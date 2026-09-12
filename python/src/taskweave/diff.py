"""スケジュール差分 (Diff) 算出および遅延原因診断モジュール.

仕様書: specs/004-actuals-and-replanning.md
"""

from __future__ import annotations

import datetime
from typing import Any

from taskweave.engine import (
    get_absences_config,
    parse_absences,
    to_date,
)


def compute_schedule_diff(
    baseline_schedule: dict[str, Any],
    replanned_schedule: dict[str, Any],
    tasks_data: list[dict[str, Any]] | None = None,
    calendar_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ベースライン計画と再計画後スケジュールの差分を計算し、遅延要因を自動診断する.

    Args:
        baseline_schedule: 初回計画結果辞書
        replanned_schedule: 再計画後結果辞書
        tasks_data: タスク原本リスト (依存関係や見積工数の参照用)
        calendar_data: カレンダー原本辞書 (個別不在の参照用)

    Returns:
        差分および診断結果の構造化辞書
    """
    b_makespan = baseline_schedule.get("makespan_workdays") or 0
    r_makespan = replanned_schedule.get("makespan_workdays") or 0
    slip_makespan = r_makespan - b_makespan

    tasks_meta = {t["id"]: t for t in (tasks_data or [])}
    calendar_absences = parse_absences(get_absences_config(calendar_data)) if calendar_data else set()

    b_tasks = baseline_schedule.get("tasks", {})
    r_tasks = replanned_schedule.get("tasks", {})
    all_task_ids = sorted(list(set(b_tasks.keys()) | set(r_tasks.keys())))

    tasks_diff: dict[str, Any] = {}
    delayed_task_ids: list[str] = []
    recommendations: list[dict[str, Any]] = []

    # 先行タスクの終了遅延マップを事前に作成
    predecessor_end_slip: dict[str, int] = {}
    for t_id in all_task_ids:
        b_t = b_tasks.get(t_id, {})
        r_t = r_tasks.get(t_id, {})
        b_end_str = b_t.get("end_date")
        r_end_str = r_t.get("end_date")
        if b_end_str and r_end_str:
            slip = (to_date(r_end_str) - to_date(b_end_str)).days
            predecessor_end_slip[t_id] = slip

    for t_id in all_task_ids:
        b_t = b_tasks.get(t_id, {})
        r_t = r_tasks.get(t_id, {})
        t_meta = tasks_meta.get(t_id, {})

        b_start_str = b_t.get("start_date")
        r_start_str = r_t.get("start_date")
        b_end_str = b_t.get("end_date")
        r_end_str = r_t.get("end_date")

        start_slip = (to_date(r_start_str) - to_date(b_start_str)).days if (b_start_str and r_start_str) else 0
        end_slip = (to_date(r_end_str) - to_date(b_end_str)).days if (b_end_str and r_end_str) else 0

        b_wcount = b_t.get("workdays_count") or 0
        r_wcount = r_t.get("workdays_count") or 0
        wcount_diff = r_wcount - b_wcount

        b_assignee = b_t.get("assigned_to")
        r_assignee = r_t.get("assigned_to")
        assignee_changed = (b_assignee != r_assignee) if (b_assignee and r_assignee) else False

        b_delay = b_t.get("delay_days") or 0
        r_delay = r_t.get("delay_days") or 0
        delay_increase = max(0, r_delay - b_delay)

        # 遅延判定
        is_delayed = (end_slip > 0) or (delay_increase > 0)
        reasons: list[str] = []
        details: list[str] = []
        primary_reason: str | None = None

        if is_delayed:
            delayed_task_ids.append(t_id)

            # 1. 工数増大 (workload_increase) の判定
            estimate = float(t_meta.get("estimate_hours") or r_t.get("estimate_hours") or 0.0)
            logged = float(r_t.get("total_logged_hours") or 0.0)
            remaining = float(r_t.get("remaining_hours") or r_t.get("estimate_hours") or 0.0)
            total_work = round(logged + remaining, 1)
            workload_excess = round(total_work - estimate, 1)

            if workload_excess > 0:
                reasons.append("workload_increase")
                details.append(
                    f"見積工数 ({estimate:.1f}h) に対し、実績および残工数合計 ({total_work:.1f}h) が超過 (+{workload_excess:.1f}h)"
                )

            # 2. メンバ欠勤 (member_absence) の判定
            if r_assignee and r_start_str and r_end_str and calendar_absences:
                r_s = to_date(r_start_str)
                r_e = to_date(r_end_str)
                matched_absences = [
                    d for (m, d) in calendar_absences if m == r_assignee and r_s <= d <= r_e
                ]
                if matched_absences:
                    reasons.append("member_absence")
                    absence_dates_str = ", ".join(d.isoformat() for d in sorted(matched_absences))
                    details.append(
                        f"担当者 '{r_assignee}' の個別不在 ({absence_dates_str}) により作業が中断・延伸"
                    )

            # 3. 先行タスク遅延の波及 (dependency_delay) の判定
            depends_on = t_meta.get("depends_on", [])
            dep_delays = []
            for dep_id in depends_on:
                slip = predecessor_end_slip.get(dep_id, 0)
                if slip > 0:
                    dep_delays.append((dep_id, slip))

            if dep_delays and start_slip > 0:
                reasons.append("dependency_delay")
                for dep_id, slip in dep_delays:
                    details.append(f"先行タスク '{dep_id}' の終了遅延 (+{slip}d) により開始が遅延")

            # 主原因 (primary_reason) の決定
            # タスク自身で工数増大があるなら工数増大が主因
            if "workload_increase" in reasons:
                primary_reason = "workload_increase"
            elif "dependency_delay" in reasons and start_slip > 0:
                primary_reason = "dependency_delay"
            elif "member_absence" in reasons:
                primary_reason = "member_absence"
            elif reasons:
                primary_reason = reasons[0]

        # 納期超過に対する推奨納期緩和 (Recommendations)
        deadline = r_t.get("deadline") or t_meta.get("deadline")
        if deadline and r_end_str:
            r_end_date = to_date(r_end_str)
            dead_date = to_date(deadline)
            if r_end_date > dead_date:
                delay_days = r_delay if r_delay > 0 else (r_end_date - dead_date).days
                recommendations.append({
                    "task_id": t_id,
                    "current_deadline": dead_date.isoformat(),
                    "recommended_deadline": r_end_date.isoformat(),
                    "delay_days": delay_days,
                    "message": f"タスク '{t_id}' の納期を {r_end_date.isoformat()} 以降に緩和することを推奨します",
                })

        tasks_diff[t_id] = {
            "task_id": t_id,
            "baseline": {
                "start_date": b_start_str,
                "end_date": b_end_str,
                "assigned_to": b_assignee,
                "workdays_count": b_wcount,
                "delay_days": b_delay,
            },
            "replanned": {
                "start_date": r_start_str,
                "end_date": r_end_str,
                "assigned_to": r_assignee,
                "workdays_count": r_wcount,
                "status": r_t.get("status", "not_started"),
                "delay_days": r_delay,
            },
            "diff": {
                "start_date_slip_days": start_slip,
                "end_date_slip_days": end_slip,
                "workdays_count_diff": wcount_diff,
                "assignee_changed": assignee_changed,
                "delay_increase_days": delay_increase,
            },
            "diagnostics": {
                "is_delayed": is_delayed,
                "primary_reason": primary_reason,
                "reasons": reasons,
                "details": details,
            },
        }

    return {
        "makespan": {
            "baseline_workdays": b_makespan,
            "replanned_workdays": r_makespan,
            "slip_workdays": slip_makespan,
        },
        "tasks": tasks_diff,
        "summary": {
            "total_tasks": len(all_task_ids),
            "delayed_tasks_count": len(delayed_task_ids),
            "delayed_task_ids": delayed_task_ids,
        },
        "recommendations": recommendations,
    }


def format_diff_summary(diff_result: dict[str, Any]) -> str:
    """差分および診断結果を人間向けテキストサマリーに整形する."""
    lines: list[str] = [
        "==================================================",
        "Taskweave Replanning & Diff Report",
        "==================================================",
    ]

    makespan = diff_result.get("makespan", {})
    b_ms = makespan.get("baseline_workdays") or 0
    r_ms = makespan.get("replanned_workdays") or 0
    slip_ms = makespan.get("slip_workdays") or 0
    sign = f"+{slip_ms}" if slip_ms >= 0 else str(slip_ms)
    lines.append(f"Makespan: {b_ms} workdays -> {r_ms} workdays ({sign} days slip)")
    lines.append("")

    summary = diff_result.get("summary", {})
    delayed_ids = summary.get("delayed_task_ids", [])

    if not delayed_ids:
        lines.append("遅延タスクはありません。計画通り進行しています。")
    else:
        lines.append(f"--- Delayed Tasks & Diagnostics ({len(delayed_ids)} tasks) ---")
        tasks = diff_result.get("tasks", {})
        for t_id in delayed_ids:
            t_data = tasks.get(t_id, {})
            b_info = t_data.get("baseline", {})
            r_info = t_data.get("replanned", {})
            diff = t_data.get("diff", {})
            diag = t_data.get("diagnostics", {})

            assignee = r_info.get("assigned_to", "unassigned")
            lines.append(f"[!] {t_id} (担当: {assignee})")

            s_slip = diff.get("start_date_slip_days") or 0
            s_sign = f"+{s_slip}" if s_slip >= 0 else str(s_slip)
            lines.append(f"    Start: {b_info.get('start_date')} -> {r_info.get('start_date')} ({s_sign}d)")

            e_slip = diff.get("end_date_slip_days") or 0
            e_sign = f"+{e_slip}" if e_slip >= 0 else str(e_slip)
            lines.append(f"    End:   {b_info.get('end_date')} -> {r_info.get('end_date')} ({e_sign}d slip)")

            p_reason = diag.get("primary_reason") or "unknown"
            lines.append(f"    Primary Reason: {p_reason}")

            for detail in diag.get("details", []):
                lines.append(f"    - {detail}")

            lines.append("")

    recs = diff_result.get("recommendations", [])
    if recs:
        lines.append("--- Recommendations (納期緩和推奨) ---")
        for rec in recs:
            lines.append(f"- [納期緩和] {rec.get('task_id')}: {rec.get('current_deadline')} -> {rec.get('recommended_deadline')} ({rec.get('delay_days')}日遅延)")
        lines.append("")

    lines.append("==================================================")
    return "\n".join(lines)
