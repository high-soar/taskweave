"""Taskweave コマンドラインインターフェース (CLI).

コマンド:
- taskweave validate [dir]
- taskweave plan [dir] [--start-date <date>] [--format text|json|mermaid|markdown] [--output <path>]
- taskweave replan [dir] --as-of <date> [--baseline <path>] [--format text|json|mermaid|markdown] [--output <path>]
- taskweave log <date> [dir] --member <id> --task <id> --hours <h> [--remaining <h>] [--status <status>] [--add]
- taskweave apply [dir] --as-of <date> [--baseline <path>] [--output <path>] [--no-backup] [--dry-run] [--update-tasks]
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any
import yaml

from taskweave.validator import (
    ProjectValidationResult,
    validate_project_data,
    validate_tasks,
)


def load_project_or_exit(dir_path: str | Path) -> ProjectValidationResult | None:
    """ディレクトリ内の原本 YAML を検証し、エラーがあれば stderr に出力して None を返す.

    原本データの読み込み・構文検証・スキーマ検証・論理整合性検証を単一パスで行う。
    """
    res = validate_project_data(dir_path)
    if not res.valid:
        err_list = res.formatted_errors or res.errors
        for err in err_list:
            sys.stderr.write(f"{err}\n")
        return None
    return res


def validate_directory(dir_path: str | Path) -> bool:
    """ディレクトリ内の原本 YAML を検証し、エラーがあれば stderr に出力する.

    Returns:
        bool: エラーが存在した場合は True、すべて成功した場合は False
    """
    res = load_project_or_exit(dir_path)
    return res is None


def format_plan_summary(plan_data: dict[str, Any]) -> str:
    """初期計画結果を人間向けテキストサマリーに整形する."""
    lines: list[str] = [
        "==================================================",
        "Taskweave Schedule Plan Report",
        "==================================================",
    ]
    status = plan_data.get("status", "UNKNOWN")
    makespan = plan_data.get("makespan_workdays") or 0
    tasks = plan_data.get("tasks", {})

    start_dates = [t["start_date"] for t in tasks.values() if t.get("start_date")]
    end_dates = [t["end_date"] for t in tasks.values() if t.get("end_date")]
    overall_start = min(start_dates) if start_dates else "-"
    overall_end = max(end_dates) if end_dates else "-"

    lines.append(f"Status: {status}")
    lines.append(f"Makespan: {makespan} workdays ({overall_start} ~ {overall_end})")
    lines.append("")
    lines.append(f"--- Tasks ({len(tasks)} tasks) ---")

    sorted_tasks = sorted(tasks.items(), key=lambda item: (item[1].get("start_date", ""), item[0]))
    for t_id, t_info in sorted_tasks:
        assignee = t_info.get("assigned_to", "unassigned")
        s_date = t_info.get("start_date", "-")
        e_date = t_info.get("end_date", "-")
        w_days = t_info.get("workdays_count", 0)
        est = t_info.get("estimate_hours", 0.0)
        delay = t_info.get("delay_days", 0)
        delay_str = f" [遅延: +{delay}稼働日]" if delay > 0 else ""
        lines.append(f"- {t_id}: {assignee} ({s_date} ~ {e_date}, {w_days} workdays, {est:.1f}h){delay_str}")

    diagnostics = plan_data.get("diagnostics", {})
    delayed_tasks = diagnostics.get("delayed_tasks", [])
    recs = diagnostics.get("recommendations", [])

    if delayed_tasks:
        lines.append("")
        lines.append(f"--- Delayed Tasks & Diagnostics ({len(delayed_tasks)} tasks) ---")
        for dt in delayed_tasks:
            lines.append(
                f"[!] {dt.get('task_id')}: 納期 {dt.get('deadline')} を {dt.get('delay_workdays')} 稼働日超過 ({dt.get('reason', '')})"
            )

    if recs:
        lines.append("")
        lines.append("--- Recommendations (納期緩和推奨) ---")
        for rec in recs:
            lines.append(
                f"- [納期緩和] {rec.get('task_id')}: 推奨納期 {rec.get('recommended_deadline')} (+{rec.get('additional_workdays_needed')}稼働日)"
            )

    lines.append("==================================================")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(prog="taskweave", description="Taskweave CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="サブコマンド")

    # validate サブコマンド
    val_parser = subparsers.add_parser("validate", help="原本 YAML データを検証する")
    val_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイル（members.yaml, tasks.yaml, calendar.yaml）が置かれたディレクトリ (デフォルト: data)",
    )

    # plan サブコマンド
    plan_parser = subparsers.add_parser(
        "plan",
        help="原本 YAML データから初期計画を計算する",
    )
    plan_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイル（members.yaml, tasks.yaml, calendar.yaml）が置かれたディレクトリ (デフォルト: data)",
    )
    plan_parser.add_argument(
        "--start-date",
        help="プロジェクト開始日 (YYYY-MM-DD 形式, 省略時は実績最古日または当日)",
    )
    plan_parser.add_argument(
        "--format",
        choices=["text", "json", "mermaid", "markdown"],
        default="text",
        help="出力フォーマット (text, json, mermaid, markdown, デフォルト: text)",
    )
    plan_parser.add_argument(
        "--output",
        help="計画結果の出力先ファイルパス (省略時は標準出力のみ)",
    )

    # replan サブコマンド
    replan_parser = subparsers.add_parser(
        "replan",
        help="起算日に基づく再計画およびベースライン差分を計算する",
    )
    replan_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイルが置かれたディレクトリ (デフォルト: data)",
    )
    replan_parser.add_argument(
        "--as-of",
        required=True,
        help="起算日 (YYYY-MM-DD 形式)",
    )
    replan_parser.add_argument(
        "--baseline",
        help="ベースライン計画 JSON ファイルのパス (省略時は実績なしで動的計算)",
    )
    replan_parser.add_argument(
        "--format",
        choices=["text", "json", "mermaid", "markdown"],
        default="text",
        help="出力フォーマット (text, json, mermaid, markdown, デフォルト: text)",
    )
    replan_parser.add_argument(
        "--output",
        help="再計画結果の出力先ファイルパス (省略時は標準出力のみ)",
    )

    # log サブコマンド
    log_parser = subparsers.add_parser(
        "log",
        help="実績工数およびタスク進捗を記録する",
    )
    log_parser.add_argument(
        "date",
        help="作業日 (YYYY-MM-DD 形式)",
    )
    log_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイルが置かれたディレクトリ (デフォルト: data)",
    )
    log_parser.add_argument(
        "--member",
        required=True,
        help="作業メンバー ID",
    )
    log_parser.add_argument(
        "--task",
        required=True,
        help="作業タスク ID",
    )
    log_parser.add_argument(
        "--hours",
        type=float,
        required=True,
        help="実績工数 (0.1時間刻みの正の数値)",
    )
    log_parser.add_argument(
        "--remaining",
        type=float,
        help="残工数 (0.0以上の0.1時間刻みの数値)",
    )
    log_parser.add_argument(
        "--status",
        choices=["not_started", "in_progress", "completed"],
        help="タスク進捗ステータス",
    )
    log_parser.add_argument(
        "--add",
        action="store_true",
        help="同一日の同一メンバ・同一タスク実績が既にある場合に加算する (デフォルト: 上書き)",
    )

    # apply サブコマンド
    apply_parser = subparsers.add_parser(
        "apply",
        help="再計画結果を検証し、確定ベースライン計画を保存・更新する",
    )
    apply_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイルが置かれたディレクトリ (デフォルト: data)",
    )
    apply_parser.add_argument(
        "--as-of",
        required=True,
        help="起算日 (YYYY-MM-DD 形式)",
    )
    apply_parser.add_argument(
        "--baseline",
        help="比較元の既存ベースライン計画 JSON ファイルのパス (省略時は既存 baseline.json または動的計算)",
    )
    apply_parser.add_argument(
        "--output",
        help="更新先ベースライン計画 JSON ファイルのパス (省略時は --baseline または <dir>/baseline.json)",
    )
    apply_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="既存ベースラインファイルや tasks.yaml のバックアップ作成をスキップする",
    )
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイル書き込みを行わず、差分サマリと適用予定内容のみを表示する",
    )
    apply_parser.add_argument(
        "--update-tasks",
        action="store_true",
        help="納期緩和推奨および担当者変更を原本 tasks.yaml に反映する",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "validate":
        has_errors = validate_directory(args.directory)
        if has_errors:
            return 1
        target_dir = Path(args.directory).resolve()
        sys.stdout.write(f"YAML 原本データの検証に成功しました: {target_dir}\n")
        return 0

    if args.subcommand == "plan":
        project_res = load_project_or_exit(args.directory)
        if project_res is None:
            return 1

        from taskweave.engine import solve_schedule, to_date

        members = project_res.members or []
        tasks = project_res.tasks or []
        calendar = project_res.calendar or {}
        actuals = project_res.actuals

        if args.start_date:
            try:
                proj_start = to_date(args.start_date)
            except Exception as err:
                sys.stderr.write(f"無効な開始日形式です (--start-date): {err}\n")
                return 1
        else:
            earliest_log_date = None
            if actuals and isinstance(actuals.get("work_logs"), list):
                log_dates = [
                    to_date(log["date"])
                    for log in actuals["work_logs"]
                    if isinstance(log, dict) and log.get("date")
                ]
                if log_dates:
                    earliest_log_date = min(log_dates)
            proj_start = earliest_log_date if earliest_log_date is not None else datetime.date.today()

        try:
            result = solve_schedule(
                members_data=members,
                tasks_data=tasks,
                calendar_data=calendar,
                project_start_date=proj_start,
            )
        except Exception as err:
            sys.stderr.write(f"計画の計算に失敗しました: {err}\n")
            return 1

        if result.get("status") not in ("OPTIMAL", "FEASIBLE"):
            sys.stderr.write(f"計画の計算が完了しませんでした (ステータス: {result.get('status')})\n")
            return 1

        if args.format == "json":
            output_content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        elif args.format == "mermaid":
            from taskweave.reporting import format_plan_mermaid

            output_content = format_plan_mermaid(result, tasks_data=tasks) + "\n"
        elif args.format == "markdown":
            from taskweave.reporting import format_plan_markdown

            output_content = format_plan_markdown(result) + "\n"
        else:
            output_content = format_plan_summary(result) + "\n"

        if args.output:
            try:
                out_path = Path(args.output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(output_content, encoding="utf-8")
            except Exception as err:
                sys.stderr.write(f"出力ファイルへの書き込みに失敗しました: {err}\n")
                return 1

        sys.stdout.write(output_content)
        return 0

    if args.subcommand == "replan":
        project_res = load_project_or_exit(args.directory)
        if project_res is None:
            return 1

        baseline_data = None
        if args.baseline:
            baseline_path = Path(args.baseline)
            try:
                with open(baseline_path, encoding="utf-8") as f:
                    baseline_data = json.load(f)
            except Exception as err:
                sys.stderr.write(f"ベースラインファイルの読み込みに失敗しました: {err}\n")
                return 1

        try:
            from taskweave.diff import format_diff_summary
            from taskweave.replan import replan

            result = replan(
                data_dir=args.directory,
                as_of_date=args.as_of,
                baseline_schedule=baseline_data,
                project_data=project_res,
            )
        except Exception as err:
            sys.stderr.write(f"再計画の実行に失敗しました: {err}\n")
            return 1

        if args.format == "json":
            output_content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        elif args.format == "mermaid":
            from taskweave.reporting import format_replan_mermaid

            output_content = format_replan_mermaid(result) + "\n"
        elif args.format == "markdown":
            from taskweave.reporting import format_replan_markdown

            output_content = format_replan_markdown(result) + "\n"
        else:
            diff_res = result.get("diff", {})
            summary_text = format_diff_summary(diff_res)
            output_content = summary_text + "\n"

        if args.output:
            try:
                out_path = Path(args.output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(output_content, encoding="utf-8")
            except Exception as err:
                sys.stderr.write(f"出力ファイルへの書き込みに失敗しました: {err}\n")
                return 1

        sys.stdout.write(output_content)
        return 0

    if args.subcommand == "log":
        from taskweave.actuals import record_work_log

        success, errors = record_work_log(
            dir_path=args.directory,
            date=args.date,
            member_id=args.member,
            task_id=args.task,
            hours=args.hours,
            remaining_hours=args.remaining,
            status=args.status,
            add=args.add,
        )
        if not success:
            for err in errors:
                sys.stderr.write(f"{err}\n")
            return 1

        sys.stdout.write(
            f"実績を actuals.yaml に記録しました (date: {args.date}, member: {args.member}, task: {args.task}, hours: {args.hours}h)\n"
        )
        return 0

    if args.subcommand == "apply":
        project_res = load_project_or_exit(args.directory)
        if project_res is None:
            return 1

        target_dir = Path(args.directory).resolve()
        out_path = Path(args.output).resolve() if args.output else (Path(args.baseline).resolve() if args.baseline else target_dir / "baseline.json")

        if args.baseline:
            baseline_path = Path(args.baseline).resolve()
        elif out_path.exists():
            baseline_path = out_path
        elif (target_dir / "baseline.json").exists():
            baseline_path = target_dir / "baseline.json"
        else:
            baseline_path = None

        baseline_data = None
        if baseline_path and baseline_path.exists():
            try:
                with open(baseline_path, encoding="utf-8") as f:
                    baseline_data = json.load(f)
            except Exception as err:
                sys.stderr.write(f"ベースラインファイルの読み込みに失敗しました: {err}\n")
                return 1

        try:
            from taskweave.diff import format_diff_summary
            from taskweave.replan import replan

            result = replan(
                data_dir=args.directory,
                as_of_date=args.as_of,
                baseline_schedule=baseline_data,
                project_data=project_res,
            )
        except Exception as err:
            sys.stderr.write(f"再計画の実行に失敗しました: {err}\n")
            return 1

        replanned_data = result.get("replanned", {})
        status = replanned_data.get("status")
        if status not in ("OPTIMAL", "FEASIBLE"):
            sys.stderr.write(f"再計画の計算が完了しませんでした (ステータス: {status})\n")
            return 1

        diff_res = result.get("diff", {})
        summary_text = format_diff_summary(diff_res)
        sys.stdout.write(summary_text + "\n")

        if args.dry_run:
            sys.stdout.write("[Dry Run] ベースラインの更新はスキップされました。\n")
            return 0

        # ベースライン更新
        replanned_json = json.dumps(replanned_data, ensure_ascii=False, indent=2) + "\n"

        if out_path.exists() and not args.no_backup:
            backup_path = out_path.with_name(out_path.name + ".bak")
            try:
                shutil.copy2(out_path, backup_path)
                sys.stdout.write(f"[Backup] 既存ベースラインのバックアップを作成しました: {backup_path}\n")
            except Exception as err:
                sys.stderr.write(f"ベースラインバックアップの作成に失敗しました: {err}\n")
                return 1

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_out = out_path.with_name(f".{out_path.name}.tmp")
            tmp_out.write_text(replanned_json, encoding="utf-8")
            tmp_out.replace(out_path)
            sys.stdout.write(f"[Apply] ベースライン計画を更新しました: {out_path}\n")
        except Exception as err:
            sys.stderr.write(f"ベースラインファイルの書き込みに失敗しました: {err}\n")
            return 1

        # 原本 tasks.yaml の更新 (--update-tasks)
        if args.update_tasks:
            tasks_file = target_dir / "tasks.yaml"
            if tasks_file.exists():
                if not args.no_backup:
                    tasks_bak = tasks_file.with_name(tasks_file.name + ".bak")
                    try:
                        shutil.copy2(tasks_file, tasks_bak)
                        sys.stdout.write(f"[Backup] 既存 tasks.yaml のバックアップを作成しました: {tasks_bak}\n")
                    except Exception as err:
                        sys.stderr.write(f"tasks.yaml バックアップの作成に失敗しました: {err}\n")
                        return 1

                try:
                    tasks_content = tasks_file.read_text(encoding="utf-8")
                    raw_data = yaml.safe_load(tasks_content) or {}
                    tasks_list = raw_data.get("tasks", []) if isinstance(raw_data, dict) else []

                    recs = diff_res.get("recommendations", [])
                    rec_deadlines = {
                        r["task_id"]: r["recommended_deadline"]
                        for r in recs
                        if "task_id" in r and "recommended_deadline" in r
                    }

                    tasks_diff = diff_res.get("tasks", {})
                    reassigned = {
                        t_id: t_info["replanned"]["assigned_to"]
                        for t_id, t_info in tasks_diff.items()
                        if t_info.get("diff", {}).get("assignee_changed") and t_info.get("replanned", {}).get("assigned_to")
                    }

                    modified_count = 0
                    for t in tasks_list:
                        tid = t.get("id")
                        if tid in rec_deadlines and t.get("deadline") != rec_deadlines[tid]:
                            t["deadline"] = rec_deadlines[tid]
                            modified_count += 1
                        if tid in reassigned and t.get("assigned_to") != reassigned[tid]:
                            t["assigned_to"] = reassigned[tid]
                            modified_count += 1

                    if modified_count > 0:
                        updated_yaml = yaml.dump(raw_data, allow_unicode=True, sort_keys=False)
                        val_res = validate_tasks(updated_yaml)
                        if not val_res.valid:
                            sys.stderr.write("更新後の tasks.yaml のスキーマ検証に失敗しました:\n")
                            for err in val_res.errors:
                                sys.stderr.write(f"  {err}\n")
                            return 1

                        tmp_yaml = tasks_file.with_name(f".{tasks_file.name}.tmp")
                        tmp_yaml.write_text(updated_yaml, encoding="utf-8")
                        tmp_yaml.replace(tasks_file)
                        sys.stdout.write(f"[Apply] tasks.yaml を更新しました ({modified_count} 箇所の変更)\n")
                    else:
                        sys.stdout.write("[Apply] tasks.yaml に更新対象の推奨・再割当はありませんでした\n")
                except Exception as err:
                    sys.stderr.write(f"tasks.yaml の更新に失敗しました: {err}\n")
                    return 1

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())


