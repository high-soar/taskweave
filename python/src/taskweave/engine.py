"""Taskweave スケジューリング計算エンジン.

OR-Tools CP-SAT を用いた制約充足・最適化ソルバー。
仕様書: specs/003-scheduling-engine.md
"""

from __future__ import annotations

import datetime
import math
from pathlib import Path
from typing import Any
import yaml
from ortools.sat.python import cp_model

WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def load_yaml(path: str | Path) -> Any:
    """指定されたパスの YAML ファイルを読み込む."""
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_project_data(data_dir: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """プロジェクト原本 YAML ディレクトリから members, tasks, calendar を読み込む."""
    p = Path(data_dir)
    members_data = load_yaml(p / "members.yaml")
    tasks_data = load_yaml(p / "tasks.yaml")
    calendar_data = load_yaml(p / "calendar.yaml")

    members = members_data.get("members", []) if isinstance(members_data, dict) else []
    tasks = tasks_data.get("tasks", []) if isinstance(tasks_data, dict) else []
    calendar = calendar_data.get("calendar", {}) if isinstance(calendar_data, dict) else {}

    return members, tasks, calendar


def build_workdays(
    start_date: datetime.date,
    num_days: int,
    workdays_config: list[str],
    holidays_config: list[dict[str, str]],
) -> list[datetime.date]:
    """指定開始日から、稼働日のみを抽出した日付リストを生成する."""
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_config}
    holiday_dates = {datetime.date.fromisoformat(h["date"]) for h in holidays_config}

    valid_days: list[datetime.date] = []
    current = start_date
    while len(valid_days) < num_days:
        if current.weekday() in allowed_weekdays and current not in holiday_dates:
            valid_days.append(current)
        current += datetime.timedelta(days=1)
    return valid_days


def count_workdays_between(
    start: datetime.date,
    end: datetime.date,
    workdays_config: list[str],
    holidays_config: list[dict[str, str]],
) -> int:
    """2つの日付間の稼働日数をカウントする (start <= date < end)."""
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_config}
    holiday_dates = {datetime.date.fromisoformat(h["date"]) for h in holidays_config}

    count = 0
    curr = start
    while curr < end:
        if curr.weekday() in allowed_weekdays and curr not in holiday_dates:
            count += 1
        curr += datetime.timedelta(days=1)
    return count


def solve_schedule(
    members_data: list[dict[str, Any]],
    tasks_data: list[dict[str, Any]],
    calendar_data: dict[str, Any],
    project_start_date: datetime.date | str,
    horizon_days: int | None = None,
    force_infeasible_deadline: bool = False,
) -> dict[str, Any]:
    """OR-Tools CP-SAT を用いて最適なスケジュールを計算する.

    Args:
        members_data: メンバ一覧
        tasks_data: タスク一覧
        calendar_data: カレンダー設定 (workdays, holidays)
        project_start_date: プロジェクト開始日
        horizon_days: 計画地平日数 (未指定時はタスク総工数から動的計算)
        force_infeasible_deadline: 診断テスト用フラグ

    Returns:
        計算結果辞書 (status, project_start_date, makespan_workdays, tasks, member_daily_work, diagnostics)
    """
    if isinstance(project_start_date, str):
        start_date = datetime.date.fromisoformat(project_start_date)
    else:
        start_date = project_start_date

    # スケール係数: 0.1h = 1 単位 (8h * 1.0 = 80, 8h * 0.8 = 64)
    scale = 10
    base_hours_per_day = 8

    # メンバ情報
    members = {m["id"]: m for m in members_data}
    member_ids = list(members.keys())
    member_capacities = {
        m["id"]: round(m.get("max_capacity", 1.0) * base_hours_per_day * scale)
        for m in members_data
    }

    # タスク情報
    tasks = {t["id"]: t for t in tasks_data}
    task_ids = list(tasks.keys())

    # 未定義依存タスクの検証 (FR-10)
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            if dep_id not in tasks:
                raise ValueError(
                    f"タスク '{t_id}' の先行タスク '{dep_id}' が tasks に定義されていません。"
                )

    # 計画地平 (Horizon) の決定 (FR-11)
    workdays_cfg = calendar_data.get("workdays", ["mon", "tue", "wed", "thu", "fri"])
    holidays_cfg = calendar_data.get("holidays", [])

    if horizon_days is None:
        min_cap = min(member_capacities.values()) if member_capacities else (base_hours_per_day * scale)
        total_workload = sum(round(t["estimate_hours"] * scale) for t in tasks_data)
        min_needed = math.ceil(total_workload / min_cap) if min_cap > 0 else 30
        horizon_days = max(30, min_needed + len(tasks_data) + 10)

    workdays = build_workdays(
        start_date=start_date,
        num_days=horizon_days,
        workdays_config=workdays_cfg,
        holidays_config=holidays_cfg,
    )

    # モデル構築
    model = cp_model.CpModel()

    # 1. assigned[t, m]: タスク t をメンバ m が担当するか
    assigned: dict[tuple[str, str], cp_model.IntVar] = {}
    for t_id in task_ids:
        for m_id in member_ids:
            assigned[t_id, m_id] = model.NewBoolVar(f"assigned_{t_id}_{m_id}")

    # 制約: 1タスクにつき担当メンバは1人 (FR-5, YAGNI)
    for t_id in task_ids:
        model.Add(sum(assigned[t_id, m_id] for m_id in member_ids) == 1)

    # スキル制約 (FR-4): required_skills を持たないメンバへの割当を禁止
    for t_id, task in tasks.items():
        req_skills = set(task.get("required_skills", []))
        for m_id, member in members.items():
            mem_skills = set(member.get("skills", []))
            if not req_skills.issubset(mem_skills):
                model.Add(assigned[t_id, m_id] == 0)

    # 2. work[t, m, d]: 日 d にタスク t でメンバ m が作業する工数 (0.1h 単位)
    work: dict[tuple[str, str, int], cp_model.IntVar] = {}
    for t_id in task_ids:
        t_est = round(tasks[t_id]["estimate_hours"] * scale)
        for m_id in member_ids:
            cap = member_capacities[m_id]
            for d in range(horizon_days):
                work[t_id, m_id, d] = model.NewIntVar(0, min(cap, t_est), f"work_{t_id}_{m_id}_{d}")

    # 制約: 担当していないメンバの日別作業時間は 0
    for t_id in task_ids:
        t_est = round(tasks[t_id]["estimate_hours"] * scale)
        for m_id in member_ids:
            for d in range(horizon_days):
                model.Add(work[t_id, m_id, d] <= t_est * assigned[t_id, m_id])

    # 制約: タスクの総作業時間 == 見積工数
    for t_id, task in tasks.items():
        t_est = round(task["estimate_hours"] * scale)
        model.Add(sum(work[t_id, m_id, d] for m_id in member_ids for d in range(horizon_days)) == t_est)

    # 制約: メンバごとの日別稼働上限 (FR-2)
    for m_id in member_ids:
        cap = member_capacities[m_id]
        for d in range(horizon_days):
            model.Add(sum(work[t_id, m_id, d] for t_id in task_ids) <= cap)

    # 3. start_day[t], end_day[t]: タスクの開始・終了稼働日インデックス
    start_day: dict[str, cp_model.IntVar] = {}
    end_day: dict[str, cp_model.IntVar] = {}
    for t_id in task_ids:
        start_day[t_id] = model.NewIntVar(0, horizon_days - 1, f"start_{t_id}")
        end_day[t_id] = model.NewIntVar(0, horizon_days - 1, f"end_{t_id}")
        model.Add(start_day[t_id] <= end_day[t_id])

        for d in range(horizon_days):
            day_work = sum(work[t_id, m_id, d] for m_id in member_ids)
            act = model.NewBoolVar(f"active_{t_id}_{d}")
            model.Add(day_work > 0).OnlyEnforceIf(act)
            model.Add(day_work == 0).OnlyEnforceIf(act.Not())

            # 作業がある日は必ず start_day <= d かつ d <= end_day
            model.Add(start_day[t_id] <= d).OnlyEnforceIf(act)
            model.Add(end_day[t_id] >= d).OnlyEnforceIf(act)

            # start_day, end_day の外側では作業できない
            before_start = model.NewBoolVar(f"before_{t_id}_{d}")
            after_end = model.NewBoolVar(f"after_{t_id}_{d}")
            model.Add(d < start_day[t_id]).OnlyEnforceIf(before_start)
            model.Add(d >= start_day[t_id]).OnlyEnforceIf(before_start.Not())
            model.Add(d > end_day[t_id]).OnlyEnforceIf(after_end)
            model.Add(d <= end_day[t_id]).OnlyEnforceIf(after_end.Not())

            model.Add(day_work == 0).OnlyEnforceIf(before_start)
            model.Add(day_work == 0).OnlyEnforceIf(after_end)

    # 制約: タスク先行依存関係 (FR-3)
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            model.Add(start_day[t_id] > end_day[dep_id])

    # 納期制約と遅延ペナルティ (FR-8)
    delay: dict[str, cp_model.IntVar] = {}
    for t_id, task in tasks.items():
        deadline_str = task.get("deadline")
        if force_infeasible_deadline:
            target_deadline_day = 1
        elif deadline_str:
            d_date = datetime.date.fromisoformat(deadline_str)
            if d_date < start_date:
                workdays_before = count_workdays_between(d_date, start_date, workdays_cfg, holidays_cfg)
                target_deadline_day = -workdays_before
            else:
                matching = [idx for idx, d in enumerate(workdays) if d <= d_date]
                target_deadline_day = max(matching) if matching else 0
        else:
            target_deadline_day = horizon_days - 1

        task_max_delay = max(horizon_days, (horizon_days - 1) - target_deadline_day)
        delay[t_id] = model.NewIntVar(0, task_max_delay, f"delay_{t_id}")
        model.Add(delay[t_id] >= end_day[t_id] - target_deadline_day)

    # 目的関数 (FR-7, FR-9):
    makespan = model.NewIntVar(0, horizon_days, "makespan")
    for t_id in task_ids:
        model.Add(makespan >= end_day[t_id])

    model.Minimize(
        sum(delay[t_id] for t_id in task_ids) * 10000
        + makespan * 100
        + sum(end_day[t] for t in task_ids) * 5
        + sum(end_day[t] - start_day[t] for t in task_ids) * 2
    )

    # ソルバー実行
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.random_seed = 42  # 決定論的再現性 (NFR-2)
    status = solver.Solve(model)

    result: dict[str, Any] = {
        "status": solver.StatusName(status),
        "project_start_date": start_date.isoformat(),
        "makespan_workdays": None,
        "tasks": {},
        "member_daily_work": {},
        "diagnostics": {
            "is_deadline_violated": False,
            "delayed_tasks": [],
        },
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["makespan_workdays"] = solver.Value(makespan) + 1

        for t_id in task_ids:
            assigned_m = [m_id for m_id in member_ids if solver.Value(assigned[t_id, m_id]) == 1][0]
            d_val = solver.Value(delay[t_id])

            daily_breakdown: dict[str, float] = {}
            active_days: list[int] = []
            for d in range(horizon_days):
                w_val = solver.Value(work[t_id, assigned_m, d])
                if w_val > 0:
                    daily_breakdown[workdays[d].isoformat()] = w_val / scale
                    active_days.append(d)

            s_idx = min(active_days) if active_days else solver.Value(start_day[t_id])
            e_idx = max(active_days) if active_days else solver.Value(end_day[t_id])

            result["tasks"][t_id] = {
                "assigned_to": assigned_m,
                "start_date": workdays[s_idx].isoformat(),
                "end_date": workdays[e_idx].isoformat(),
                "workdays_count": e_idx - s_idx + 1,
                "actual_active_days": len(active_days),
                "estimate_hours": float(tasks[t_id]["estimate_hours"]),
                "daily_hours": daily_breakdown,
                "deadline": tasks[t_id].get("deadline"),
                "delay_days": d_val,
            }
            if d_val > 0:
                result["diagnostics"]["is_deadline_violated"] = True
                result["diagnostics"]["delayed_tasks"].append(
                    {
                        "task_id": t_id,
                        "delay_workdays": d_val,
                        "deadline": tasks[t_id].get("deadline"),
                        "projected_end_date": workdays[e_idx].isoformat(),
                        "reason": f"制約充足により納期 ({tasks[t_id].get('deadline')}) を {d_val} 稼働日超過",
                    }
                )

        # メンバ日別集計
        for m_id in member_ids:
            result["member_daily_work"][m_id] = {}
            for d in range(horizon_days):
                total_w = sum(solver.Value(work[t_id, m_id, d]) for t_id in task_ids)
                if total_w > 0:
                    result["member_daily_work"][m_id][workdays[d].isoformat()] = total_w / scale

    return result
