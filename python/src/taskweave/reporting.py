"""Taskweave レポーティングモジュール.

Mermaid ガントチャート出力および Markdown 表形式出力を提供する.
仕様書: specs/005-agent-cli-and-reporting.md (Issue #41)
"""

from __future__ import annotations

from typing import Any


def format_plan_mermaid(
    plan_data: dict[str, Any],
    tasks_data: list[dict[str, Any]] | None = None,
) -> str:
    """初期計画結果を Mermaid gantt 記法に整形する."""
    lines: list[str] = [
        "```mermaid",
        "gantt",
        "    title Taskweave Schedule Plan",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %Y-%m-%d",
        "    excludes weekends",
    ]

    deps_map: dict[str, list[str]] = {}
    if tasks_data:
        for t in tasks_data:
            if isinstance(t, dict) and t.get("id"):
                deps_map[t["id"]] = [d for d in t.get("depends_on", []) if d]

    tasks: dict[str, Any] = plan_data.get("tasks", {})
    by_member: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    for t_id, t_info in tasks.items():
        member = t_info.get("assigned_to") or "unassigned"
        by_member.setdefault(member, []).append((t_id, t_info))

    sorted_members = sorted(by_member.keys(), key=lambda m: (m == "unassigned", m))

    for member in sorted_members:
        lines.append("")
        lines.append(f"    section {member}")
        member_tasks = sorted(
            by_member[member],
            key=lambda item: (item[1].get("start_date", ""), item[0]),
        )
        for t_id, t_info in member_tasks:
            s_date = t_info.get("start_date", "-")
            e_date = t_info.get("end_date", "-")
            delay = t_info.get("delay_days", 0)

            tags: list[str] = []
            if delay > 0:
                tags.append("crit")

            deps = deps_map.get(t_id, [])
            tag_prefix = ", ".join(tags)
            tag_str = f" {tag_prefix}, " if tag_prefix else " "

            if deps:
                after_str = f"after {' '.join(deps)}"
                lines.append(f"    {t_id} :{tag_str}{t_id}, {after_str}, {e_date}")
            else:
                lines.append(f"    {t_id} :{tag_str}{t_id}, {s_date}, {e_date}")

    lines.append("```")
    return "\n".join(lines)


def format_plan_markdown(plan_data: dict[str, Any]) -> str:
    """初期計画結果を Markdown 表形式に整形する."""
    lines: list[str] = [
        "# スケジュール計画レポート (Taskweave Schedule Plan)",
        "",
        "## 全体サマリ",
        "| 項目 | 内容 |",
        "| --- | --- |",
    ]

    status = plan_data.get("status", "UNKNOWN")
    makespan = plan_data.get("makespan_workdays") or 0
    tasks: dict[str, Any] = plan_data.get("tasks", {})

    start_dates = [t["start_date"] for t in tasks.values() if t.get("start_date")]
    end_dates = [t["end_date"] for t in tasks.values() if t.get("end_date")]
    overall_start = min(start_dates) if start_dates else "-"
    overall_end = max(end_dates) if end_dates else "-"

    total_est = sum(float(t.get("estimate_hours") or 0.0) for t in tasks.values())

    lines.append(f"| ステータス | {status} |")
    lines.append(f"| Makespan | {makespan} 稼働日 ({overall_start} ~ {overall_end}) |")
    lines.append(f"| タスク総数 | {len(tasks)} |")
    lines.append(f"| 総見積工数 | {total_est:.1f} 時間 |")
    lines.append("")

    lines.append("## タスク一覧")
    lines.append("| タスクID | 担当者 | 開始日 | 終了日 | 稼働日数 | 見積工数 | 納期 | 遅延 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

    sorted_tasks = sorted(tasks.items(), key=lambda item: (item[1].get("start_date", ""), item[0]))
    for t_id, t_info in sorted_tasks:
        assignee = t_info.get("assigned_to") or "unassigned"
        s_date = t_info.get("start_date", "-")
        e_date = t_info.get("end_date", "-")
        w_days = t_info.get("workdays_count", 0)
        est = float(t_info.get("estimate_hours") or 0.0)
        deadline = t_info.get("deadline") or "-"
        delay = t_info.get("delay_days", 0)
        delay_str = f"+{delay}日" if delay > 0 else "-"
        lines.append(f"| {t_id} | {assignee} | {s_date} | {e_date} | {w_days} | {est:.1f}h | {deadline} | {delay_str} |")

    lines.append("")
    lines.append("## 担当者別工数サマリ")
    lines.append("| 担当者 | 割当タスク数 | 合計工数 |")
    lines.append("| --- | --- | --- |")

    member_summary: dict[str, list[float]] = {}
    for t_info in tasks.values():
        m = t_info.get("assigned_to") or "unassigned"
        member_summary.setdefault(m, []).append(float(t_info.get("estimate_hours") or 0.0))

    for m in sorted(member_summary.keys(), key=lambda x: (x == "unassigned", x)):
        m_tasks = member_summary[m]
        lines.append(f"| {m} | {len(m_tasks)} | {sum(m_tasks):.1f}h |")

    diagnostics = plan_data.get("diagnostics", {})
    delayed_tasks = diagnostics.get("delayed_tasks", [])
    recs = diagnostics.get("recommendations", [])

    if delayed_tasks:
        lines.append("")
        lines.append("## 遅延タスク診断")
        lines.append("| タスクID | 納期 | 予測終了日 | 超過稼働日 | 原因 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for dt in delayed_tasks:
            lines.append(
                f"| {dt.get('task_id')} | {dt.get('deadline')} | {dt.get('projected_end_date')} | "
                f"{dt.get('delay_workdays')} | {dt.get('reason', '')} |"
            )

    if recs:
        lines.append("")
        lines.append("## 納期緩和推奨 (Recommendations)")
        lines.append("| タスクID | 現納期 | 推奨納期 | 追加必要日数 |")
        lines.append("| --- | --- | --- | --- |")
        for rec in recs:
            lines.append(
                f"| {rec.get('task_id')} | {rec.get('current_deadline') or '-'} | "
                f"{rec.get('recommended_deadline')} | +{rec.get('additional_workdays_needed')}稼働日 |"
            )

    return "\n".join(lines)


def format_replan_mermaid(replan_result: dict[str, Any]) -> str:
    """再計画結果を過去実績・残工数が可視化された Mermaid gantt 記法に整形する."""
    lines: list[str] = [
        "```mermaid",
        "gantt",
        "    title Taskweave Replanned Schedule",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %Y-%m-%d",
        "    excludes weekends",
    ]

    replanned = replan_result.get("replanned", {})
    diff = replan_result.get("diff", {})
    tasks_diff = diff.get("tasks", {})
    as_of = replanned.get("as_of_date", "")

    tasks: dict[str, Any] = replanned.get("tasks", {})
    by_member: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    for t_id, t_info in tasks.items():
        member = t_info.get("assigned_to") or "unassigned"
        by_member.setdefault(member, []).append((t_id, t_info))

    sorted_members = sorted(by_member.keys(), key=lambda m: (m == "unassigned", m))

    for member in sorted_members:
        lines.append("")
        lines.append(f"    section {member}")
        member_tasks = sorted(
            by_member[member],
            key=lambda item: (item[1].get("start_date", ""), item[0]),
        )
        for t_id, t_info in member_tasks:
            s_date = t_info.get("start_date", "-")
            e_date = t_info.get("end_date", "-")
            status = t_info.get("status", "not_started")
            remaining_hours = float(t_info.get("remaining_hours") or 0.0)
            daily_hours: dict[str, float] = t_info.get("daily_hours", {})

            is_delayed = bool(tasks_diff.get(t_id, {}).get("diagnostics", {}).get("is_delayed"))
            delay_prefix = "crit, " if is_delayed else ""

            if status in ("completed", "done"):
                lines.append(f"    {t_id} [完了] : done, {t_id}, {s_date}, {e_date}")
            elif status == "in_progress":
                past_days = [d for d, h in daily_hours.items() if d <= as_of and h > 0] if daily_hours and as_of else []
                future_days = [d for d, h in daily_hours.items() if d > as_of and h > 0] if daily_hours and as_of else []

                if past_days and future_days:
                    lines.append(
                        f"    {t_id} [実績] : done, {t_id}-actual, {min(past_days)}, {max(past_days)}"
                    )
                    lines.append(
                        f"    {t_id} [残工数] : {delay_prefix}active, {t_id}, {min(future_days)}, {max(future_days)}"
                    )
                elif past_days:
                    lines.append(
                        f"    {t_id} [実績] : done, {t_id}-actual, {min(past_days)}, {max(past_days)}"
                    )
                elif future_days:
                    lines.append(
                        f"    {t_id} [残工数] : {delay_prefix}active, {t_id}, {min(future_days)}, {max(future_days)}"
                    )
                else:
                    lines.append(f"    {t_id} : {delay_prefix}active, {t_id}, {s_date}, {e_date}")
            else:
                tag_str = f" {delay_prefix}" if delay_prefix else " "
                lines.append(f"    {t_id} :{tag_str}{t_id}, {s_date}, {e_date}")

    lines.append("```")
    return "\n".join(lines)


def format_replan_markdown(replan_result: dict[str, Any]) -> str:
    """再計画結果および差分・診断を Markdown 表形式に整形する."""
    lines: list[str] = [
        "# スケジュール再計画レポート (Taskweave Replanning Report)",
        "",
        "## ベースライン比較サマリ",
        "| 項目 | ベースライン | 再計画 | 差分 (Slip) |",
        "| --- | --- | --- | --- |",
    ]

    baseline = replan_result.get("baseline", {})
    replanned = replan_result.get("replanned", {})
    diff = replan_result.get("diff", {})

    makespan = diff.get("makespan", {})
    b_ms = makespan.get("baseline_workdays") or baseline.get("makespan_workdays") or 0
    r_ms = makespan.get("replanned_workdays") or replanned.get("makespan_workdays") or 0
    slip_ms = makespan.get("slip_workdays") or (r_ms - b_ms)
    sign_ms = f"+{slip_ms}" if slip_ms >= 0 else str(slip_ms)

    b_tasks = baseline.get("tasks", {})
    r_tasks = replanned.get("tasks", {})
    b_count = len(b_tasks)
    r_count = len(r_tasks)
    task_diff = r_count - b_count
    sign_task = f"+{task_diff}" if task_diff >= 0 else str(task_diff)

    summary = diff.get("summary", {})
    delayed_ids = summary.get("delayed_task_ids", [])

    b_delayed_count = sum(1 for t in b_tasks.values() if (t.get("delay_days") or 0) > 0)
    r_delayed_count = sum(1 for t in r_tasks.values() if (t.get("delay_days") or 0) > 0)
    delay_slip = r_delayed_count - b_delayed_count
    sign_delay = f"+{delay_slip}" if delay_slip >= 0 else str(delay_slip)

    lines.append(f"| Makespan | {b_ms} 稼働日 | {r_ms} 稼働日 | {sign_ms} 稼働日 |")
    lines.append(f"| タスク総数 | {b_count} | {r_count} | {sign_task} |")
    lines.append(f"| 遅延タスク数 | {b_delayed_count} | {r_delayed_count} | {sign_delay} |")
    lines.append("")

    lines.append("## 遅延タスク診断 (Delayed Tasks & Diagnostics)")
    if not delayed_ids:
        lines.append("遅延タスクはありません。計画通り進行しています。")
    else:
        lines.append("| タスクID | 担当者 | ベースライン終了日 | 再計画終了日 | スリップ日数 | 主原因 | 詳細 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        reason_map = {
            "workload_increase": "工数超過 (workload_increase)",
            "member_absence": "メンバ欠勤 (member_absence)",
            "dependency_delay": "先行遅延 (dependency_delay)",
        }
        tasks_diff = diff.get("tasks", {})
        for t_id in delayed_ids:
            t_data = tasks_diff.get(t_id, {})
            b_info = t_data.get("baseline", {})
            r_info = t_data.get("replanned", {})
            d_info = t_data.get("diff", {})
            diag = t_data.get("diagnostics", {})

            assignee = r_info.get("assigned_to") or b_info.get("assigned_to") or "unassigned"
            b_end = b_info.get("end_date") or "-"
            r_end = r_info.get("end_date") or "-"
            e_slip = d_info.get("end_date_slip_days") or 0
            slip_str = f"+{e_slip}日" if e_slip >= 0 else f"{e_slip}日"
            p_reason = diag.get("primary_reason") or "unknown"
            p_reason_str = reason_map.get(p_reason, p_reason)
            details_str = "<br>".join(diag.get("details", [])) or "-"

            lines.append(f"| {t_id} | {assignee} | {b_end} | {r_end} | {slip_str} | {p_reason_str} | {details_str} |")

    lines.append("")
    lines.append("## 再計画タスク一覧 (Replanned Tasks)")
    lines.append("| タスクID | 担当者 | ステータス | 開始日 | 終了日 | 稼働日数 | 実績工数 | 残工数 | 納期 | 遅延 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    sorted_r_tasks = sorted(r_tasks.items(), key=lambda item: (item[1].get("start_date", ""), item[0]))
    for t_id, t_info in sorted_r_tasks:
        assignee = t_info.get("assigned_to") or "unassigned"
        status = t_info.get("status", "not_started")
        s_date = t_info.get("start_date", "-")
        e_date = t_info.get("end_date", "-")
        w_days = t_info.get("workdays_count", 0)
        logged = float(t_info.get("total_logged_hours") or 0.0)
        remaining = float(t_info.get("remaining_hours") or 0.0)
        deadline = t_info.get("deadline") or "-"
        delay = t_info.get("delay_days", 0)
        delay_str = f"+{delay}日" if delay > 0 else "-"
        lines.append(
            f"| {t_id} | {assignee} | {status} | {s_date} | {e_date} | {w_days} | "
            f"{logged:.1f}h | {remaining:.1f}h | {deadline} | {delay_str} |"
        )

    recs = diff.get("recommendations", [])
    if recs:
        lines.append("")
        lines.append("## 納期緩和推奨 (Recommendations)")
        lines.append("| タスクID | 現納期 | 推奨納期 | 遅延日数 | 推奨内容 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for rec in recs:
            lines.append(
                f"| {rec.get('task_id')} | {rec.get('current_deadline') or '-'} | "
                f"{rec.get('recommended_deadline')} | {rec.get('delay_days')}日 | {rec.get('message', '')} |"
            )

    return "\n".join(lines)
