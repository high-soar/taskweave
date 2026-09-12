"""再計画実行およびベースライン差分・診断の統合モジュール.

仕様書: specs/004-actuals-and-replanning.md
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from taskweave.diff import compute_schedule_diff
from taskweave.engine import load_project_data, solve_schedule, to_date


def replan(
    data_dir: str | Path,
    as_of_date: datetime.date | str,
    baseline_schedule: dict[str, Any] | None = None,
    project_start_date: datetime.date | str | None = None,
) -> dict[str, Any]:
    """ディレクトリ内の原本および実績データを読み込み、再計画と差分算出を実行する.

    Args:
        data_dir: members.yaml, tasks.yaml, calendar.yaml (および actuals.yaml) が置かれたディレクトリ
        as_of_date: 起算日 (YYYY-MM-DD または datetime.date)
        baseline_schedule: 事前計算されたベースライン計画 (未指定時は実績なしで動的計算)
        project_start_date: プロジェクト開始日 (未指定時は実績の最古日付または as_of_date)

    Returns:
        {"baseline": baseline_dict, "replanned": replanned_dict, "diff": diff_dict}
    """
    as_of = to_date(as_of_date)
    members, tasks, calendar, actuals = load_project_data(data_dir, include_actuals=True)

    # プロジェクト開始日の決定
    if project_start_date is not None:
        proj_start = to_date(project_start_date)
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
        proj_start = earliest_log_date if earliest_log_date is not None else as_of

    if proj_start > as_of:
        proj_start = as_of

    # ベースラインの取得または計算
    if baseline_schedule is not None:
        baseline_res = baseline_schedule
    else:
        baseline_res = solve_schedule(
            members_data=members,
            tasks_data=tasks,
            calendar_data=calendar,
            project_start_date=proj_start,
        )

    # 再計画の計算
    replanned_res = solve_schedule(
        members_data=members,
        tasks_data=tasks,
        calendar_data=calendar,
        project_start_date=proj_start,
        as_of_date=as_of,
        actuals_data=actuals,
    )

    # 差分および診断の算出
    diff_res = compute_schedule_diff(
        baseline_schedule=baseline_res,
        replanned_schedule=replanned_res,
        tasks_data=tasks,
        calendar_data=calendar,
    )

    return {
        "baseline": baseline_res,
        "replanned": replanned_res,
        "diff": diff_res,
    }
