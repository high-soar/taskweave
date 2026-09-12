"""Taskweave スケジューリング計算エンジン.

OR-Tools CP-SAT を用いた制約充足・最適化ソルバー。
仕様書: specs/003-scheduling-engine.md
"""

from __future__ import annotations

from collections import deque
import datetime
import math
from pathlib import Path
from typing import Any, Literal, overload
import yaml
from ortools.sat.python import cp_model

from taskweave.validator import (
    resolve_task_progress,
    validate_project_data,
    validate_schedule_inputs,
)

WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def to_date(val: str | datetime.date) -> datetime.date:
    """文字列または datetime.date を datetime.date オブジェクトに統一する."""
    if isinstance(val, datetime.date):
        return val
    return datetime.date.fromisoformat(val)


def load_yaml(path: str | Path) -> Any:
    """指定されたパスの YAML ファイルを読み込む."""
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


@overload
def load_project_data(
    data_dir: str | Path,
    include_actuals: Literal[False] = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]: ...


@overload
def load_project_data(
    data_dir: str | Path,
    include_actuals: Literal[True],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]: ...


@overload
def load_project_data(
    data_dir: str | Path,
    include_actuals: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]: ...


def load_project_data(
    data_dir: str | Path,
    include_actuals: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    """プロジェクト原本 YAML ディレクトリから members, tasks, calendar (および任意で actuals) を読み込む."""
    result = validate_project_data(data_dir)
    if not result.valid:
        raise ValueError(f"プロジェクトデータの検証に失敗しました: {'; '.join(result.errors)}")
    if include_actuals:
        return result.members or [], result.tasks or [], result.calendar or {}, result.actuals
    return result.members or [], result.tasks or [], result.calendar or {}


def parse_holiday_dates(holidays_config: list[dict[str, Any]]) -> set[datetime.date]:
    """祝日設定リストを検証し、datetime.date のセットを生成する."""
    holiday_dates: set[datetime.date] = set()
    for h in holidays_config:
        if not isinstance(h, dict) or "date" not in h or h["date"] is None:
            raise ValueError(f"calendar.holidays の各項目には 'date' フィールドが必須です: {h}")
        holiday_dates.add(to_date(h["date"]))
    return holiday_dates


def build_workdays(
    start_date: datetime.date,
    num_days: int,
    workdays_config: list[str],
    holidays_config: list[dict[str, Any]],
) -> list[datetime.date]:
    """指定開始日から、稼働日のみを抽出した日付リストを生成する."""
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_config if w in WEEKDAY_MAP}
    if not allowed_weekdays:
        raise ValueError("calendar.workdays に有効な稼働曜日が指定されていません。")
    holiday_dates = parse_holiday_dates(holidays_config)

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
    holidays_config: list[dict[str, Any]],
) -> int:
    """2つの日付間の稼働日数をカウントする (start <= date < end)."""
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_config if w in WEEKDAY_MAP}
    if not allowed_weekdays:
        raise ValueError("calendar.workdays に有効な稼働曜日が指定されていません。")
    holiday_dates = parse_holiday_dates(holidays_config)

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
    as_of_date: datetime.date | str | None = None,
    actuals_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """OR-Tools CP-SAT を用いて最適なスケジュールを計算する.

    Args:
        members_data: メンバ一覧
        tasks_data: タスク一覧
        calendar_data: カレンダー設定 (workdays, holidays)
        project_start_date: プロジェクト開始日
        horizon_days: 計画地平日数 (未指定時はタスク総工数から動的計算)
        force_infeasible_deadline: 診断テスト用フラグ
        as_of_date: 起算日 (未指定時はプロジェクト開始日からの全量計画)
        actuals_data: 実績データ (work_logs, task_progress)

    Returns:
        計算結果辞書 (status, project_start_date, as_of_date, makespan_workdays, tasks, member_daily_work, diagnostics)
    """
    start_date = to_date(project_start_date)
    as_of = to_date(as_of_date) if as_of_date is not None else None
    if as_of is not None and as_of < start_date:
        raise ValueError(f"as_of_date は project_start_date 以降である必要があります: as_of={as_of}, start_date={start_date}")

    if as_of is not None:
        return _solve_replan(
            members_data=members_data,
            tasks_data=tasks_data,
            calendar_data=calendar_data,
            project_start_date=start_date,
            as_of_date=as_of,
            actuals_data=actuals_data,
            horizon_days=horizon_days,
            force_infeasible_deadline=force_infeasible_deadline,
        )

    # 入力データの検証 (validator へ集約)
    validate_schedule_inputs(members_data, tasks_data, calendar_data)

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
        raw_skills = task.get("required_skills")
        req_skills = set(raw_skills) if isinstance(raw_skills, list) else set()
        for m_id, member in members.items():
            mem_skills = set(member.get("skills") or [])
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

    # 制約: 担当していないメンバの日別作業時間は 0 (タスク・メンバ単位で集約し、線形制約数を削減)
    for t_id in task_ids:
        t_est = round(tasks[t_id]["estimate_hours"] * scale)
        for m_id in member_ids:
            model.Add(sum(work[t_id, m_id, d] for d in range(horizon_days)) <= t_est * assigned[t_id, m_id])

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

            # 作業がある日は必ず start_day <= d かつ d <= end_day (外側では act=False となり day_work=0 が保証される)
            model.Add(start_day[t_id] <= d).OnlyEnforceIf(act)
            model.Add(end_day[t_id] >= d).OnlyEnforceIf(act)

    # 制約: タスク先行依存関係 (FR-3)
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            model.Add(start_day[t_id] > end_day[dep_id])

    # 納期制約と遅延ペナルティ (FR-8)
    delay: dict[str, cp_model.IntVar] = {}
    task_deadline_days: dict[str, int] = {}
    first_workday = workdays[0]
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_cfg if w in WEEKDAY_MAP}
    holiday_dates = parse_holiday_dates(holidays_cfg)

    for t_id, task in tasks.items():
        deadline_raw = task.get("deadline")
        if force_infeasible_deadline:
            target_deadline_day = 1
        elif deadline_raw:
            d_date = to_date(deadline_raw)
            if d_date >= first_workday:
                matching = [idx for idx, d in enumerate(workdays) if d <= d_date]
                target_deadline_day = max(matching) if matching else 0
            else:
                # 最初の稼働日より前の納期（開始日が非稼働日の場合や過去納期）:
                # d_date 以前の直近稼働日を求め、そこから first_workday までの稼働日数差を負のインデックスとする
                curr = d_date
                while curr.weekday() not in allowed_weekdays or curr in holiday_dates:
                    curr -= datetime.timedelta(days=1)
                workdays_before = count_workdays_between(curr, first_workday, workdays_cfg, holidays_cfg)
                target_deadline_day = -workdays_before
        else:
            target_deadline_day = horizon_days - 1

        task_deadline_days[t_id] = target_deadline_day
        task_max_delay = max(horizon_days, (horizon_days - 1) - target_deadline_day)
        delay[t_id] = model.NewIntVar(0, task_max_delay, f"delay_{t_id}")

        # [R1]: delay[t_id] を max(0, end_day[t_id] - target_deadline_day) と等値化
        diff = model.NewIntVar(-task_max_delay, task_max_delay, f"diff_{t_id}")
        model.Add(diff == end_day[t_id] - target_deadline_day)
        model.AddMaxEquality(delay[t_id], [0, diff])

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

    # 初期解ヒントの生成 (NFR-1, NFR-2, R3: 単一ワーカーでも大規模問題で10秒以内にFEASIBLE解を保証)
    in_degree = {t_id: 0 for t_id in task_ids}
    dependents: dict[str, list[str]] = {t_id: [] for t_id in task_ids}
    for t_id, task in tasks.items():
        for dep_id in task.get("depends_on", []):
            if dep_id in dependents:
                dependents[dep_id].append(t_id)
                in_degree[t_id] += 1

    queue = deque(t_id for t_id in task_ids if in_degree[t_id] == 0)
    topo_order: list[str] = []
    while queue:
        curr = queue.popleft()
        topo_order.append(curr)
        for nxt in dependents[curr]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(topo_order) < len(task_ids):
        remaining = [t for t in task_ids if t not in topo_order]
        topo_order.extend(remaining)

    member_next_free_day = {m_id: 0 for m_id in member_ids}
    hint_end_day: dict[str, int] = {}

    for t_id in topo_order:
        min_start = 0
        for dep_id in tasks[t_id].get("depends_on", []):
            if dep_id in hint_end_day:
                min_start = max(min_start, hint_end_day[dep_id] + 1)

        raw_skills = tasks[t_id].get("required_skills")
        req_skills = set(raw_skills) if isinstance(raw_skills, list) else set()
        capable_members = [
            m_id
            for m_id in member_ids
            if req_skills.issubset(set(members[m_id].get("skills") or []))
        ]
        if not capable_members:
            continue

        best_m = capable_members[0]
        best_start = horizon_days
        for m_id in capable_members:
            s = max(min_start, member_next_free_day[m_id])
            if s < best_start:
                best_start = s
                best_m = m_id

        t_est = round(tasks[t_id]["estimate_hours"] * scale)
        cap = member_capacities[best_m]
        days_needed = math.ceil(t_est / cap) if cap > 0 else 1

        if best_start + days_needed <= horizon_days:
            model.AddHint(assigned[t_id, best_m], 1)
            for other_m in member_ids:
                if other_m != best_m:
                    model.AddHint(assigned[t_id, other_m], 0)

            model.AddHint(start_day[t_id], best_start)
            end_s = best_start + days_needed - 1
            model.AddHint(end_day[t_id], end_s)
            hint_end_day[t_id] = end_s
            member_next_free_day[best_m] = end_s + 1

            remaining_work = t_est
            for offset in range(days_needed):
                d = best_start + offset
                w = min(cap, remaining_work)
                model.AddHint(work[t_id, best_m, d], w)
                remaining_work -= w

    # ソルバー実行
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 1  # 決定論的再現性 (NFR-2, 単一ワーカーで探索順序を決定論化)
    solver.parameters.random_seed = 42  # 決定論的再現性 (NFR-2)
    status = solver.Solve(model)

    result: dict[str, Any] = {
        "status": solver.StatusName(status),
        "project_start_date": start_date.isoformat(),
        "as_of_date": None,
        "makespan_workdays": None,
        "tasks": {},
        "member_daily_work": {},
        "diagnostics": {
            "is_deadline_violated": False,
            "total_delay_workdays": 0,
            "delayed_tasks": [],
            "recommendations": [],
        },
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["makespan_workdays"] = solver.Value(makespan) + 1

        for t_id in task_ids:
            assigned_m = [m_id for m_id in member_ids if solver.Value(assigned[t_id, m_id]) == 1][0]

            daily_breakdown: dict[str, float] = {}
            active_days: list[int] = []
            for d in range(horizon_days):
                w_val = solver.Value(work[t_id, assigned_m, d])
                if w_val > 0:
                    daily_breakdown[workdays[d].isoformat()] = w_val / scale
                    active_days.append(d)

            s_idx = min(active_days) if active_days else solver.Value(start_day[t_id])
            e_idx = max(active_days) if active_days else solver.Value(end_day[t_id])

            t_est = round(tasks[t_id]["estimate_hours"] * scale)
            normalized_estimate = round(t_est / scale, 1)
            raw_deadline = tasks[t_id].get("deadline")
            normalized_deadline = to_date(raw_deadline).isoformat() if raw_deadline else None

            # [R1]: 実際の終了インデックス e_idx と deadline_day_val から正確な遅延日数を算出
            deadline_day_val = task_deadline_days.get(t_id, horizon_days - 1)
            if raw_deadline is not None:
                actual_delay = max(0, e_idx - deadline_day_val)
            else:
                actual_delay = 0

            result["tasks"][t_id] = {
                "assigned_to": assigned_m,
                "start_date": workdays[s_idx].isoformat(),
                "end_date": workdays[e_idx].isoformat(),
                "workdays_count": e_idx - s_idx + 1,
                "actual_active_days": len(active_days),
                "estimate_hours": normalized_estimate,
                "remaining_hours": normalized_estimate,
                "total_logged_hours": 0.0,
                "status": "not_started",
                "daily_hours": daily_breakdown,
                "deadline": normalized_deadline,
                "delay_days": actual_delay,
            }

            if actual_delay > 0:
                result["diagnostics"]["is_deadline_violated"] = True

                # 遅延原因（ボトルネック）の診断 (FR-8, Issue #15)
                reasons: list[str] = []
                if deadline_day_val < 0:
                    reasons.append(f"納期 ({normalized_deadline}) がプロジェクト開始日以前に設定されている")
                else:
                    blocking_deps: list[str] = []
                    for dep_id in tasks[t_id].get("depends_on", []):
                        dep_e_idx = solver.Value(end_day[dep_id])
                        cap_hours = member_capacities[assigned_m] / scale
                        min_workdays_needed = math.ceil(tasks[t_id]["estimate_hours"] / cap_hours)
                        if dep_e_idx >= deadline_day_val or dep_e_idx + min_workdays_needed > deadline_day_val:
                            blocking_deps.append(dep_id)
                    if blocking_deps:
                        reasons.append(f"先行タスク {', '.join(blocking_deps)} の完了待ち")

                    cap_hours = member_capacities[assigned_m] / scale
                    min_workdays_needed = math.ceil(tasks[t_id]["estimate_hours"] / cap_hours)
                    if min_workdays_needed > (deadline_day_val + 1):
                        reasons.append(f"日別稼働上限 ({cap_hours}h/日) に対する工数不足")
                    elif not blocking_deps:
                        reasons.append("担当メンバのリソース競合または日別稼働上限")

                reason_text = (
                    "および".join(reasons) + f"により納期 ({normalized_deadline}) を {actual_delay} 稼働日超過"
                    if reasons
                    else f"制約充足により納期 ({normalized_deadline}) を {actual_delay} 稼働日超過"
                )

                result["diagnostics"]["delayed_tasks"].append(
                    {
                        "task_id": t_id,
                        "delay_workdays": actual_delay,
                        "deadline": normalized_deadline,
                        "projected_end_date": workdays[e_idx].isoformat(),
                        "reason": reason_text,
                    }
                )
                result["diagnostics"]["recommendations"].append(
                    {
                        "task_id": t_id,
                        "action": "extend_deadline",
                        "recommended_deadline": workdays[e_idx].isoformat(),
                        "additional_workdays_needed": actual_delay,
                    }
                )

        result["diagnostics"]["total_delay_workdays"] = sum(
            d["delay_workdays"] for d in result["diagnostics"]["delayed_tasks"]
        )

        # メンバ日別集計
        for m_id in member_ids:
            result["member_daily_work"][m_id] = {}
            for d in range(horizon_days):
                total_w = sum(solver.Value(work[t_id, m_id, d]) for t_id in task_ids)
                if total_w > 0:
                    result["member_daily_work"][m_id][workdays[d].isoformat()] = total_w / scale

    return result


def _build_completed_task_result(
    t_id: str,
    task: dict[str, Any],
    progress: dict[str, Any],
    daily: dict[str, float],
    assigned_m: str,
    project_start_date: datetime.date,
    workdays_cfg: list[str],
    holidays_cfg: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None, datetime.date]:
    """完了タスクの出力辞書と遅延診断情報を構築するヘルパー."""
    s_date = min(daily.keys()) if daily else project_start_date.isoformat()
    e_date = max(daily.keys()) if daily else s_date
    s_d = to_date(s_date)
    e_d = to_date(e_date)

    w_count = count_workdays_between(s_d, e_d + datetime.timedelta(days=1), workdays_cfg, holidays_cfg)
    raw_dl = task.get("deadline")
    norm_dl = to_date(raw_dl).isoformat() if raw_dl else None
    act_delay = 0
    if norm_dl and e_d > to_date(norm_dl):
        act_delay = count_workdays_between(
            to_date(norm_dl) + datetime.timedelta(days=1),
            e_d + datetime.timedelta(days=1),
            workdays_cfg,
            holidays_cfg,
        )

    task_result = {
        "assigned_to": assigned_m,
        "start_date": s_date,
        "end_date": e_date,
        "workdays_count": max(1, w_count),
        "actual_active_days": len(daily),
        "estimate_hours": round(float(task["estimate_hours"]), 1),
        "remaining_hours": 0.0,
        "total_logged_hours": progress["total_logged_hours"],
        "status": "completed",
        "daily_hours": daily,
        "deadline": norm_dl,
        "delay_days": act_delay,
    }
    delayed_diag = None
    if act_delay > 0:
        delayed_diag = {
            "task_id": t_id,
            "delay_workdays": act_delay,
            "deadline": norm_dl,
            "projected_end_date": e_date,
            "reason": f"納期 ({norm_dl}) を {act_delay} 稼働日超過",
        }
    return task_result, delayed_diag, e_d


def _solve_replan(
    members_data: list[dict[str, Any]],
    tasks_data: list[dict[str, Any]],
    calendar_data: dict[str, Any],
    project_start_date: datetime.date,
    as_of_date: datetime.date,
    actuals_data: dict[str, Any] | None,
    horizon_days: int | None = None,
    force_infeasible_deadline: bool = False,
) -> dict[str, Any]:
    """起算日 (As-of Date) に基づく実績固定と未完了タスクの再計画計算 (Issue #26)."""
    validate_schedule_inputs(members_data, tasks_data, calendar_data)

    scale = 10
    base_hours_per_day = 8

    members = {m["id"]: m for m in members_data}
    member_ids = list(members.keys())
    member_capacities = {
        m["id"]: round(m.get("max_capacity", 1.0) * base_hours_per_day * scale)
        for m in members_data
    }

    tasks = {t["id"]: t for t in tasks_data}

    workdays_cfg = calendar_data.get("workdays", ["mon", "tue", "wed", "thu", "fri"])
    holidays_cfg = calendar_data.get("holidays", [])
    allowed_weekdays = {WEEKDAY_MAP[w] for w in workdays_cfg if w in WEEKDAY_MAP}
    holiday_dates = parse_holiday_dates(holidays_cfg)
    first_proj_workday = build_workdays(project_start_date, 1, workdays_cfg, holidays_cfg)[0]

    # 実績データの抽出と時間軸分割 (AC-1)
    raw_work_logs = (actuals_data.get("work_logs") or []) if isinstance(actuals_data, dict) else []
    raw_task_progress = (actuals_data.get("task_progress") or []) if isinstance(actuals_data, dict) else []

    past_work_logs = [
        wl for wl in raw_work_logs
        if isinstance(wl, dict) and to_date(wl.get("date")) < as_of_date
    ]
    filtered_actuals = {"work_logs": past_work_logs, "task_progress": raw_task_progress}
    resolved_progress = resolve_task_progress(tasks_data, actuals=filtered_actuals)
    progress_by_task = {p["task_id"]: p for p in resolved_progress}

    past_daily_by_task: dict[str, dict[str, float]] = {t["id"]: {} for t in tasks_data}
    task_past_member: dict[str, str] = {}
    member_past_daily: dict[str, dict[str, float]] = {m["id"]: {} for m in members_data}

    for wl in past_work_logs:
        t_id = wl["task_id"]
        m_id = wl["member_id"]
        d_str = to_date(wl["date"]).isoformat()
        h = float(wl["hours"])
        past_daily_by_task[t_id][d_str] = round(past_daily_by_task[t_id].get(d_str, 0.0) + h, 1)
        task_past_member.setdefault(t_id, m_id)  # FR-5 / FR-7: 1タスク1担当者前提
        if m_id in member_past_daily:
            member_past_daily[m_id][d_str] = round(member_past_daily[m_id].get(d_str, 0.0) + h, 1)

    # タスクの分類 (完了タスク vs 未来再計画タスク) (AC-2)
    completed_task_ids: list[str] = []
    future_task_ids: list[str] = []

    for t in tasks_data:
        t_id = t["id"]
        p = progress_by_task[t_id]
        if p["status"] == "completed" or p["remaining_hours"] <= 0.0:
            completed_task_ids.append(t_id)
        else:
            future_task_ids.append(t_id)

    # 全タスク完了時の早期終了最適化 (FR-15)
    if not future_task_ids:
        result_tasks: dict[str, Any] = {}
        diagnostics: dict[str, Any] = {
            "is_deadline_violated": False,
            "total_delay_workdays": 0,
            "delayed_tasks": [],
            "recommendations": [],
        }
        all_end_dates: list[datetime.date] = []

        for t in tasks_data:
            t_id = t["id"]
            p = progress_by_task[t_id]
            daily = past_daily_by_task.get(t_id, {})
            assigned_m = task_past_member.get(t_id)
            if not assigned_m:
                req = set(t.get("required_skills") or [])
                capable = [m["id"] for m in members_data if req.issubset(set(m.get("skills") or []))]
                assigned_m = capable[0] if capable else members_data[0]["id"]

            task_res, delayed_diag, e_d = _build_completed_task_result(
                t_id, t, p, daily, assigned_m, project_start_date, workdays_cfg, holidays_cfg
            )
            result_tasks[t_id] = task_res
            all_end_dates.append(e_d)
            if delayed_diag:
                diagnostics["is_deadline_violated"] = True
                diagnostics["delayed_tasks"].append(delayed_diag)

        diagnostics["total_delay_workdays"] = sum(d["delay_workdays"] for d in diagnostics["delayed_tasks"])
        max_e_d = max(all_end_dates) if all_end_dates else first_proj_workday
        makespan_wd = count_workdays_between(first_proj_workday, max_e_d + datetime.timedelta(days=1), workdays_cfg, holidays_cfg)

        return {
            "status": "OPTIMAL",
            "project_start_date": project_start_date.isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "makespan_workdays": max(1, makespan_wd),
            "tasks": result_tasks,
            "member_daily_work": member_past_daily,
            "diagnostics": diagnostics,
        }

    # 未来計画地平 (Horizon) の決定
    if horizon_days is None:
        min_cap = min(member_capacities.values()) if member_capacities else (base_hours_per_day * scale)
        total_workload = sum(round(progress_by_task[t_id]["remaining_hours"] * scale) for t_id in future_task_ids)
        min_needed = math.ceil(total_workload / min_cap) if min_cap > 0 else 30
        future_horizon_days = max(30, min_needed + len(future_task_ids) + 10)
    else:
        future_horizon_days = horizon_days

    # 未来稼働日リスト (as_of_date 以降)
    future_workdays = build_workdays(
        start_date=as_of_date,
        num_days=future_horizon_days,
        workdays_config=workdays_cfg,
        holidays_config=holidays_cfg,
    )

    model = cp_model.CpModel()

    # 1. assigned[t, m]
    assigned: dict[tuple[str, str], cp_model.IntVar] = {}
    for t_id in future_task_ids:
        for m_id in member_ids:
            assigned[t_id, m_id] = model.NewBoolVar(f"assigned_{t_id}_{m_id}")

    for t_id in future_task_ids:
        model.Add(sum(assigned[t_id, m_id] for m_id in member_ids) == 1)

    # スキル制約および着手済みタスクの担当メンバ固定 (AC-3, AC-4)
    for t_id in future_task_ids:
        p = progress_by_task[t_id]
        pinned_m = task_past_member.get(t_id)
        if p["total_logged_hours"] > 0 and pinned_m:
            model.Add(assigned[t_id, pinned_m] == 1)
            for other_m in member_ids:
                if other_m != pinned_m:
                    model.Add(assigned[t_id, other_m] == 0)
        else:
            raw_skills = tasks[t_id].get("required_skills")
            req_skills = set(raw_skills) if isinstance(raw_skills, list) else set()
            for m_id, member in members.items():
                mem_skills = set(member.get("skills") or [])
                if not req_skills.issubset(mem_skills):
                    model.Add(assigned[t_id, m_id] == 0)

    # 2. work[t, m, d]: 残工数 (remaining_hours) のみを変数化
    work: dict[tuple[str, str, int], cp_model.IntVar] = {}
    for t_id in future_task_ids:
        t_rem = round(progress_by_task[t_id]["remaining_hours"] * scale)
        for m_id in member_ids:
            cap = member_capacities[m_id]
            for d in range(future_horizon_days):
                work[t_id, m_id, d] = model.NewIntVar(0, min(cap, t_rem), f"work_{t_id}_{m_id}_{d}")

    for t_id in future_task_ids:
        t_rem = round(progress_by_task[t_id]["remaining_hours"] * scale)
        for m_id in member_ids:
            model.Add(sum(work[t_id, m_id, d] for d in range(future_horizon_days)) <= t_rem * assigned[t_id, m_id])

    for t_id in future_task_ids:
        t_rem = round(progress_by_task[t_id]["remaining_hours"] * scale)
        model.Add(sum(work[t_id, m_id, d] for m_id in member_ids for d in range(future_horizon_days)) == t_rem)

    for m_id in member_ids:
        cap = member_capacities[m_id]
        for d in range(future_horizon_days):
            model.Add(sum(work[t_id, m_id, d] for t_id in future_task_ids) <= cap)

    # 3. start_day, end_day
    start_day: dict[str, cp_model.IntVar] = {}
    end_day: dict[str, cp_model.IntVar] = {}
    for t_id in future_task_ids:
        start_day[t_id] = model.NewIntVar(0, future_horizon_days - 1, f"start_{t_id}")
        end_day[t_id] = model.NewIntVar(0, future_horizon_days - 1, f"end_{t_id}")
        model.Add(start_day[t_id] <= end_day[t_id])

        for d in range(future_horizon_days):
            day_work = sum(work[t_id, m_id, d] for m_id in member_ids)
            act = model.NewBoolVar(f"active_{t_id}_{d}")
            model.Add(day_work > 0).OnlyEnforceIf(act)
            model.Add(day_work == 0).OnlyEnforceIf(act.Not())

            model.Add(start_day[t_id] <= d).OnlyEnforceIf(act)
            model.Add(end_day[t_id] >= d).OnlyEnforceIf(act)

    # タスク先行依存関係 (FR-13, AC-4: 完了済みタスクへの依存は解決済み)
    for t_id in future_task_ids:
        for dep_id in tasks[t_id].get("depends_on", []):
            if dep_id in future_task_ids:
                model.Add(start_day[t_id] > end_day[dep_id])

    # 納期制約と遅延ペナルティ
    delay: dict[str, cp_model.IntVar] = {}
    task_deadline_days: dict[str, int] = {}
    first_future_workday = future_workdays[0]

    for t_id in future_task_ids:
        task = tasks[t_id]
        deadline_raw = task.get("deadline")
        if force_infeasible_deadline:
            target_deadline_day = 1
        elif deadline_raw:
            d_date = to_date(deadline_raw)
            if d_date >= first_future_workday:
                matching = [idx for idx, d in enumerate(future_workdays) if d <= d_date]
                target_deadline_day = max(matching) if matching else 0
            else:
                curr = d_date
                while curr.weekday() not in allowed_weekdays or curr in holiday_dates:
                    curr -= datetime.timedelta(days=1)
                workdays_before = count_workdays_between(curr, first_future_workday, workdays_cfg, holidays_cfg)
                target_deadline_day = -workdays_before
        else:
            target_deadline_day = future_horizon_days - 1

        task_deadline_days[t_id] = target_deadline_day
        task_max_delay = max(future_horizon_days, (future_horizon_days - 1) - target_deadline_day)
        delay[t_id] = model.NewIntVar(0, task_max_delay, f"delay_{t_id}")

        diff = model.NewIntVar(-task_max_delay, task_max_delay, f"diff_{t_id}")
        model.Add(diff == end_day[t_id] - target_deadline_day)
        model.AddMaxEquality(delay[t_id], [0, diff])

    makespan = model.NewIntVar(0, future_horizon_days, "makespan")
    for t_id in future_task_ids:
        model.Add(makespan >= end_day[t_id])

    model.Minimize(
        sum(delay[t_id] for t_id in future_task_ids) * 10000
        + makespan * 100
        + sum(end_day[t] for t in future_task_ids) * 5
        + sum(end_day[t] - start_day[t] for t in future_task_ids) * 2
    )

    # 初期解ヒントの生成 (NFR-2, 単一ワーカー探索順序の安定化)
    in_degree = {t_id: 0 for t_id in future_task_ids}
    dependents: dict[str, list[str]] = {t_id: [] for t_id in future_task_ids}
    for t_id in future_task_ids:
        for dep_id in tasks[t_id].get("depends_on", []):
            if dep_id in dependents:
                dependents[dep_id].append(t_id)
                in_degree[t_id] += 1

    queue = deque([t_id for t_id in future_task_ids if in_degree[t_id] == 0])
    topo_order: list[str] = []
    while queue:
        curr = queue.popleft()
        topo_order.append(curr)
        for nxt in dependents[curr]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(topo_order) < len(future_task_ids):
        remaining = [t for t in future_task_ids if t not in topo_order]
        topo_order.extend(remaining)

    member_next_free_day = {m_id: 0 for m_id in member_ids}
    hint_end_day: dict[str, int] = {}

    for t_id in topo_order:
        min_start = 0
        for dep_id in tasks[t_id].get("depends_on", []):
            if dep_id in hint_end_day:
                min_start = max(min_start, hint_end_day[dep_id] + 1)

        p = progress_by_task[t_id]
        pinned_m = task_past_member.get(t_id) if p["total_logged_hours"] > 0 else None

        if pinned_m:
            best_m = pinned_m
            best_start = max(min_start, member_next_free_day[best_m])
        else:
            raw_skills = tasks[t_id].get("required_skills")
            req_skills = set(raw_skills) if isinstance(raw_skills, list) else set()
            capable_members = [
                m_id
                for m_id in member_ids
                if req_skills.issubset(set(members[m_id].get("skills") or []))
            ]
            if not capable_members:
                continue

            best_m = capable_members[0]
            best_start = future_horizon_days
            for m_id in capable_members:
                s = max(min_start, member_next_free_day[m_id])
                if s < best_start:
                    best_start = s
                    best_m = m_id

        t_rem = round(p["remaining_hours"] * scale)
        cap = member_capacities[best_m]
        days_needed = math.ceil(t_rem / cap) if cap > 0 else 1

        if best_start + days_needed <= future_horizon_days:
            model.AddHint(assigned[t_id, best_m], 1)
            for other_m in member_ids:
                if other_m != best_m:
                    model.AddHint(assigned[t_id, other_m], 0)

            model.AddHint(start_day[t_id], best_start)
            end_s = best_start + days_needed - 1
            model.AddHint(end_day[t_id], end_s)
            hint_end_day[t_id] = end_s
            member_next_free_day[best_m] = end_s + 1

            remaining_work = t_rem
            for offset in range(days_needed):
                d = best_start + offset
                w = min(cap, remaining_work)
                model.AddHint(work[t_id, best_m, d], w)
                remaining_work -= w

    # ソルバー実行 (AC-6)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.Solve(model)

    result = {
        "status": solver.StatusName(status),
        "project_start_date": project_start_date.isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "makespan_workdays": None,
        "tasks": {},
        "member_daily_work": {},
        "diagnostics": {
            "is_deadline_violated": False,
            "total_delay_workdays": 0,
            "delayed_tasks": [],
            "recommendations": [],
        },
    }

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # 1. 完了済みタスクの出力構築 (AC-2)
        for t_id in completed_task_ids:
            p = progress_by_task[t_id]
            daily = past_daily_by_task.get(t_id, {})
            assigned_m = task_past_member.get(t_id)
            if not assigned_m:
                req = set(tasks[t_id].get("required_skills") or [])
                capable = [m["id"] for m in members_data if req.issubset(set(m.get("skills") or []))]
                assigned_m = capable[0] if capable else members_data[0]["id"]

            task_res, delayed_diag, _ = _build_completed_task_result(
                t_id, tasks[t_id], p, daily, assigned_m, project_start_date, workdays_cfg, holidays_cfg
            )
            result["tasks"][t_id] = task_res
            if delayed_diag:
                result["diagnostics"]["is_deadline_violated"] = True
                result["diagnostics"]["delayed_tasks"].append(delayed_diag)

        # 2. 未来タスクの出力構築 (AC-3, AC-4)
        for t_id in future_task_ids:
            assigned_m = [m_id for m_id in member_ids if solver.Value(assigned[t_id, m_id]) == 1][0]
            future_daily: dict[str, float] = {}
            active_days: list[int] = []
            for d in range(future_horizon_days):
                w_val = solver.Value(work[t_id, assigned_m, d])
                if w_val > 0:
                    future_daily[future_workdays[d].isoformat()] = w_val / scale
                    active_days.append(d)

            combined_daily = dict(past_daily_by_task.get(t_id, {}))
            combined_daily.update(future_daily)

            if combined_daily:
                s_date = min(combined_daily.keys())
                e_date = max(combined_daily.keys())
            else:
                s_date = future_workdays[solver.Value(start_day[t_id])].isoformat()
                e_date = future_workdays[solver.Value(end_day[t_id])].isoformat()

            s_d = to_date(s_date)
            e_d = to_date(e_date)
            w_count = count_workdays_between(s_d, e_d + datetime.timedelta(days=1), workdays_cfg, holidays_cfg)

            p = progress_by_task[t_id]
            raw_deadline = tasks[t_id].get("deadline")
            norm_deadline = to_date(raw_deadline).isoformat() if raw_deadline else None
            deadline_day_val = task_deadline_days.get(t_id, future_horizon_days - 1)
            actual_delay = max(0, solver.Value(end_day[t_id]) - deadline_day_val) if raw_deadline is not None else 0

            result["tasks"][t_id] = {
                "assigned_to": assigned_m,
                "start_date": s_date,
                "end_date": e_date,
                "workdays_count": max(1, w_count),
                "actual_active_days": len(combined_daily),
                "estimate_hours": round(float(tasks[t_id]["estimate_hours"]), 1),
                "remaining_hours": p["remaining_hours"],
                "total_logged_hours": p["total_logged_hours"],
                "status": p["status"],
                "daily_hours": combined_daily,
                "deadline": norm_deadline,
                "delay_days": actual_delay,
            }

            if actual_delay > 0:
                result["diagnostics"]["is_deadline_violated"] = True
                reasons: list[str] = []
                if deadline_day_val < 0:
                    reasons.append(f"納期 ({norm_deadline}) が起算日以前に設定されている")
                else:
                    blocking_deps: list[str] = []
                    for dep_id in tasks[t_id].get("depends_on", []):
                        if dep_id in future_task_ids:
                            dep_e_idx = solver.Value(end_day[dep_id])
                            cap_hours = member_capacities[assigned_m] / scale
                            min_workdays_needed = math.ceil(p["remaining_hours"] / cap_hours)
                            if dep_e_idx >= deadline_day_val or dep_e_idx + min_workdays_needed > deadline_day_val:
                                blocking_deps.append(dep_id)
                    if blocking_deps:
                        reasons.append(f"先行タスク {', '.join(blocking_deps)} の完了待ち")

                    cap_hours = member_capacities[assigned_m] / scale
                    min_workdays_needed = math.ceil(p["remaining_hours"] / cap_hours)
                    if min_workdays_needed > (deadline_day_val + 1):
                        reasons.append(f"日別稼働上限 ({cap_hours}h/日) に対する工数不足")
                    elif not blocking_deps:
                        reasons.append("担当メンバのリソース競合または日別稼働上限")

                reason_text = (
                    "および".join(reasons) + f"により納期 ({norm_deadline}) を {actual_delay} 稼働日超過"
                    if reasons
                    else f"制約充足により納期 ({norm_deadline}) を {actual_delay} 稼働日超過"
                )

                result["diagnostics"]["delayed_tasks"].append({
                    "task_id": t_id,
                    "delay_workdays": actual_delay,
                    "deadline": norm_deadline,
                    "projected_end_date": e_date,
                    "reason": reason_text,
                })
                result["diagnostics"]["recommendations"].append({
                    "task_id": t_id,
                    "action": "extend_deadline",
                    "recommended_deadline": e_date,
                    "additional_workdays_needed": actual_delay,
                })

        result["diagnostics"]["total_delay_workdays"] = sum(
            d["delay_workdays"] for d in result["diagnostics"]["delayed_tasks"]
        )

        # 3. Makespan (全タスクの終了日から算出)
        all_end_dates = [to_date(t_info["end_date"]) for t_info in result["tasks"].values()]
        max_end = max(all_end_dates) if all_end_dates else first_proj_workday
        result["makespan_workdays"] = max(1, count_workdays_between(first_proj_workday, max_end + datetime.timedelta(days=1), workdays_cfg, holidays_cfg))

        # 4. member_daily_work (過去実績 + 未来計画の合算)
        for m_id in member_ids:
            combined_m_daily = dict(member_past_daily.get(m_id, {}))
            for d in range(future_horizon_days):
                tot = sum(solver.Value(work[t, m_id, d]) for t in future_task_ids)
                if tot > 0:
                    combined_m_daily[future_workdays[d].isoformat()] = tot / scale
            result["member_daily_work"][m_id] = combined_m_daily

    return result

