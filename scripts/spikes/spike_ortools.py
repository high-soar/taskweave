#!/usr/bin/env python3
"""OR-Tools CP-SAT スケジューリング計算モデルの技術検証（Spike）スクリプト.

検証論点:
1. 時間の離散化単位 (0.1h 単位スケーリング、round 丸め)
2. 稼働上限 (max_capacity) と先行依存関係 (depends_on)
3. チームカレンダー (土日・祝日のスキップ)
4. スキル制約 (required_skills)
5. 納期制約 (deadline) と Infeasible 時の遅延・ボトルネック診断
6. 動的計画地平 (Horizon) 計算と未定義依存タスクの検知
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


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_workdays(
    start_date: datetime.date,
    num_days: int,
    workdays_config: list[str],
    holidays_config: list[dict[str, str]],
) -> list[datetime.date]:
    """指定開始日から、稼働日のみを抽出したリストを生成する."""
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
    """2つの日付間の稼働日数をカウントする（start <= date < end）."""
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
    project_start_date: datetime.date,
    horizon_days: int | None = None,
    force_infeasible_deadline: bool = False,
) -> dict[str, Any]:
    """OR-Tools CP-SAT でスケジュールを解く."""
    # スケール係数: 0.1h = 1 単位 (8h * 1.0 = 80, 8h * 0.8 = 64)
    SCALE = 10
    BASE_HOURS_PER_DAY = 8

    # メンバ情報
    members = {m["id"]: m for m in members_data}
    member_ids = list(members.keys())
    member_capacities = {
        m["id"]: round(m.get("max_capacity", 1.0) * BASE_HOURS_PER_DAY * SCALE)
        for m in members_data
    }

    # タスク情報
    tasks = {t["id"]: t for t in tasks_data}
    task_ids = list(tasks.keys())

    # 未定義依存タスクの検知（FR-7 準拠の入力エラー検証）
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            if dep_id not in tasks:
                raise ValueError(
                    f"タスク '{t_id}' の先行タスク '{dep_id}' が tasks に定義されていません。"
                )

    # 計画地平（Horizon）の決定
    workdays_cfg = calendar_data.get("workdays", ["mon", "tue", "wed", "thu", "fri"])
    holidays_cfg = calendar_data.get("holidays", [])

    if horizon_days is None:
        min_cap = min(member_capacities.values()) if member_capacities else (BASE_HOURS_PER_DAY * SCALE)
        total_workload = sum(round(t["estimate_hours"] * SCALE) for t in tasks_data)
        min_needed = math.ceil(total_workload / min_cap) if min_cap > 0 else 30
        horizon_days = max(30, min_needed + len(tasks_data) + 10)

    workdays = build_workdays(
        start_date=project_start_date,
        num_days=horizon_days,
        workdays_config=workdays_cfg,
        holidays_config=holidays_cfg,
    )

    # モデル構築
    model = cp_model.CpModel()

    # 決定変数:
    # 1. assigned[t, m]: タスク t をメンバ m が担当するか (0 or 1)
    assigned = {}
    for t_id in task_ids:
        for m_id in member_ids:
            assigned[t_id, m_id] = model.NewBoolVar(f"assigned_{t_id}_{m_id}")

    # 制約: 1タスクにつき担当メンバは1人 (YAGNI原則)
    for t_id in task_ids:
        model.Add(sum(assigned[t_id, m_id] for m_id in member_ids) == 1)

    # スキル制約: タスクの required_skills を持たないメンバへの割当を禁止
    for t_id, task in tasks.items():
        req_skills = set(task.get("required_skills", []))
        for m_id, member in members.items():
            mem_skills = set(member.get("skills", []))
            if not req_skills.issubset(mem_skills):
                model.Add(assigned[t_id, m_id] == 0)

    # 2. work[t, m, d]: 日 d にタスク t でメンバ m が作業する時間 (0.1h 単位)
    work = {}
    for t_id in task_ids:
        t_est = round(tasks[t_id]["estimate_hours"] * SCALE)
        for m_id in member_ids:
            cap = member_capacities[m_id]
            for d in range(horizon_days):
                work[t_id, m_id, d] = model.NewIntVar(0, min(cap, t_est), f"work_{t_id}_{m_id}_{d}")

    # 制約: 担当していないメンバの日別作業時間は 0
    for t_id in task_ids:
        t_est = round(tasks[t_id]["estimate_hours"] * SCALE)
        for m_id in member_ids:
            for d in range(horizon_days):
                model.Add(work[t_id, m_id, d] <= t_est * assigned[t_id, m_id])

    # 制約: タスクの総作業時間 == 見積工数
    for t_id, task in tasks.items():
        t_est = round(task["estimate_hours"] * SCALE)
        model.Add(sum(work[t_id, m_id, d] for m_id in member_ids for d in range(horizon_days)) == t_est)

    # 制約: メンバごとの日別稼働上限
    for m_id in member_ids:
        cap = member_capacities[m_id]
        for d in range(horizon_days):
            model.Add(sum(work[t_id, m_id, d] for t_id in task_ids) <= cap)

    # 3. start_day[t], end_day[t]: タスクの開始日と終了日 (稼働日インデックス)
    start_day = {}
    end_day = {}
    is_active = {}
    for t_id in task_ids:
        start_day[t_id] = model.NewIntVar(0, horizon_days - 1, f"start_{t_id}")
        end_day[t_id] = model.NewIntVar(0, horizon_days - 1, f"end_{t_id}")
        model.Add(start_day[t_id] <= end_day[t_id])

        for d in range(horizon_days):
            day_work = sum(work[t_id, m_id, d] for m_id in member_ids)
            act = model.NewBoolVar(f"active_{t_id}_{d}")
            is_active[t_id, d] = act
            model.Add(day_work > 0).OnlyEnforceIf(act)
            model.Add(day_work == 0).OnlyEnforceIf(act.Not())

            # 作業がある日は必ず start_day <= d かつ d <= end_day
            model.Add(start_day[t_id] <= d).OnlyEnforceIf(act)
            model.Add(end_day[t_id] >= d).OnlyEnforceIf(act)

            # start_day, end_day の外側では作業できない (作業量 = 0)
            before_start = model.NewBoolVar(f"before_{t_id}_{d}")
            after_end = model.NewBoolVar(f"after_{t_id}_{d}")
            model.Add(d < start_day[t_id]).OnlyEnforceIf(before_start)
            model.Add(d >= start_day[t_id]).OnlyEnforceIf(before_start.Not())
            model.Add(d > end_day[t_id]).OnlyEnforceIf(after_end)
            model.Add(d <= end_day[t_id]).OnlyEnforceIf(after_end.Not())

            model.Add(day_work == 0).OnlyEnforceIf(before_start)
            model.Add(day_work == 0).OnlyEnforceIf(after_end)

    # 先行依存関係制約: depends_on のタスク完了後に開始
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            # 先行タスクの終了日翌稼働日以降に開始
            model.Add(start_day[t_id] > end_day[dep_id])

    # 納期制約と遅延ペナルティ変数 (Infeasible 診断用)
    delay = {}
    for t_id, task in tasks.items():
        deadline_str = task.get("deadline")
        if force_infeasible_deadline:
            target_deadline_day = 1
        elif deadline_str:
            d_date = datetime.date.fromisoformat(deadline_str)
            if d_date < project_start_date:
                # 開始日前の納期: 開始日までの稼働日数を負のインデックスとして算出
                workdays_before = count_workdays_between(d_date, project_start_date, workdays_cfg, holidays_cfg)
                target_deadline_day = -workdays_before
            else:
                # カレンダー上の最も近い稼働日インデックスを探す
                matching = [idx for idx, d in enumerate(workdays) if d <= d_date]
                target_deadline_day = max(matching) if matching else 0
        else:
            target_deadline_day = horizon_days - 1

        # 各タスクの納期に応じて遅延変数の上限を動的に導出 (極端な過去納期でも INFEASIBLE を回避)
        task_max_delay = max(horizon_days, (horizon_days - 1) - target_deadline_day)
        delay[t_id] = model.NewIntVar(0, task_max_delay, f"delay_{t_id}")
        model.Add(delay[t_id] >= end_day[t_id] - target_deadline_day)


    # 目的関数:
    # 1. 納期遅延の最小化 (最優先: 重み 10000)
    # 2. 全体工期 (Makespan) の最小化 (重み 100)
    # 3. 各タスクの早期完了 (sum(end_day), 重み 5)
    # 4. 各タスクの所要スパンの最小化 (中抜け抑制: sum(end_day - start_day), 重み 2)
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
    status = solver.Solve(model)

    result: dict[str, Any] = {
        "status": solver.StatusName(status),
        "project_start_date": project_start_date.isoformat(),
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

            daily_breakdown = {}
            active_days = []
            for d in range(horizon_days):
                w_val = solver.Value(work[t_id, assigned_m, d])
                if w_val > 0:
                    daily_breakdown[workdays[d].isoformat()] = w_val / SCALE
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
                    result["member_daily_work"][m_id][workdays[d].isoformat()] = total_w / SCALE

    return result


def main() -> None:
    data_dir = Path("examples/basic")
    members_data = load_yaml(data_dir / "members.yaml")["members"]
    tasks_data = load_yaml(data_dir / "tasks.yaml")["tasks"]
    calendar_data = load_yaml(data_dir / "calendar.yaml")["calendar"]

    project_start = datetime.date(2026, 9, 1)  # 2026年9月1日（火）

    print("=" * 60)
    print("【Spike 1: 正常系スケジュール最適化検証】")
    print("=" * 60)
    res_normal = solve_schedule(members_data, tasks_data, calendar_data, project_start)
    print(f"ステータス: {res_normal['status']}")
    print(f"プロジェクト開始日: {res_normal['project_start_date']}")
    print(f"総所要稼働日数 (Makespan): {res_normal['makespan_workdays']} 日\n")

    for t_id, t_info in res_normal["tasks"].items():
        print(f"タスク: {t_id}")
        print(f"  担当者: {t_info['assigned_to']}")
        print(f"  期間: {t_info['start_date']} 〜 {t_info['end_date']} ({t_info['workdays_count']} 稼働日)")
        print(f"  見積工数: {t_info['estimate_hours']}h")
        print(f"  日別工数: {t_info['daily_hours']}")
        print(f"  納期: {t_info['deadline']} (遅延: {t_info['delay_days']}日)")

    print("\nメンバ日別稼働時間:")
    for m_id, days in res_normal["member_daily_work"].items():
        print(f"  メンバ {m_id}:")
        for d_str, hours in days.items():
            print(f"    {d_str}: {hours}h")

    print("\n" + "=" * 60)
    print("【Spike 2: 納期超過・Infeasible 診断検証 (無理な納期)】")
    print("=" * 60)
    res_infeasible = solve_schedule(
        members_data, tasks_data, calendar_data, project_start, force_infeasible_deadline=True
    )
    print(f"ステータス: {res_infeasible['status']}")
    print(f"納期違反フラグ: {res_infeasible['diagnostics']['is_deadline_violated']}")
    print(f"遅延タスク検出数: {len(res_infeasible['diagnostics']['delayed_tasks'])} 件")
    for d_info in res_infeasible["diagnostics"]["delayed_tasks"]:
        print(f"  [ボトルネック警告] タスク {d_info['task_id']}: {d_info['delay_workdays']} 稼働日遅延 (予測完了: {d_info['projected_end_date']})")

    print("\n" + "=" * 60)
    print("【Spike 3: 並行タスク & 小数稼働上限 (Bob: 0.8 capacity = 6.4h/日) 検証】")
    print("=" * 60)
    tasks_with_devops = list(tasks_data) + [
        {
            "id": "task-ci",
            "title": "CI/CD パイプライン構築",
            "estimate_hours": 12,
            "required_skills": ["devops"],
            "depends_on": [],
            "deadline": "2026-09-20",
        }
    ]
    res_parallel = solve_schedule(members_data, tasks_with_devops, calendar_data, project_start)
    print(f"ステータス: {res_parallel['status']}")
    print(f"総所要稼働日数 (Makespan): {res_parallel['makespan_workdays']} 日\n")

    for t_id, t_info in res_parallel["tasks"].items():
        print(f"タスク: {t_id}")
        print(f"  担当者: {t_info['assigned_to']}")
        print(f"  期間: {t_info['start_date']} 〜 {t_info['end_date']} ({t_info['workdays_count']} 稼働日)")
        print(f"  日別工数: {t_info['daily_hours']}")


if __name__ == "__main__":
    main()
