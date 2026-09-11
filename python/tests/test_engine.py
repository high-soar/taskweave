"""Taskweave 計算エンジン (Scheduling Engine) の単体テスト.

仕様: specs/003-scheduling-engine.md
受入基準 (Issue #12):
- シナリオ 1: 原本 YAML の読み込み
- シナリオ 2: メンバの1日稼働上限の遵守
- シナリオ 3: タスク先行依存関係の遵守
- シナリオ 4: 各タスクの開始日・終了日・担当メンバ・日別割当工数の出力
- シナリオ 5: タスク全体の完了期間 (Makespan) 最小化
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest

from taskweave import (
    count_workdays_between,
    load_project_data,
    load_yaml,
    solve_schedule,
)


@pytest.fixture
def repo_root() -> Path:
    # .worktrees/<name>/python/tests/test_engine.py -> repo root is parent.parent.parent
    # または通常の python/tests/test_engine.py -> repo root is parent.parent
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "examples" / "basic").exists():
            return cur
        cur = cur.parent
    raise RuntimeError("Repository root with examples/basic not found")


@pytest.fixture
def basic_data(repo_root: Path) -> tuple[list[dict], list[dict], dict]:
    data_dir = repo_root / "examples" / "basic"
    members = load_yaml(data_dir / "members.yaml")["members"]
    tasks = load_yaml(data_dir / "tasks.yaml")["tasks"]
    calendar = load_yaml(data_dir / "calendar.yaml")["calendar"]
    return members, tasks, calendar


def test_scenario_1_load_yaml(repo_root: Path):
    """シナリオ 1: 原本 YAML を正しく読み込めること."""
    data_dir = repo_root / "examples" / "basic"
    members, tasks, calendar = load_project_data(data_dir)

    assert len(members) >= 2
    assert any(m["id"] == "alice" for m in members)
    assert any(m["id"] == "bob" for m in members)

    assert len(tasks) >= 2
    assert any(t["id"] == "task-api" for t in tasks)
    assert any(t["id"] == "task-ui" for t in tasks)

    assert "workdays" in calendar
    assert "holidays" in calendar


def test_scenario_2_capacity_constraint(basic_data):
    """シナリオ 2: メンバの1日稼働上限（標準8h × max_capacity）を超える割当が発生しないこと."""
    members, tasks, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    result = solve_schedule(members, tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"

    # Alice: max_capacity 1.0 -> 8.0h/日
    # Bob: max_capacity 0.8 -> 6.4h/日
    for m in members:
        m_id = m["id"]
        max_daily_allowed = m.get("max_capacity", 1.0) * 8.0
        daily_work = result["member_daily_work"].get(m_id, {})
        for day_str, hours in daily_work.items():
            assert hours <= max_daily_allowed + 1e-6, f"{m_id} on {day_str}: {hours} > {max_daily_allowed}"


def test_scenario_3_and_5_dependency_and_makespan(basic_data):
    """シナリオ 3 & 5: 先行タスク完了後に後続タスクが開始され、Makespanが最小化されること."""
    members, tasks, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)  # 2026-09-01 (火)

    result = solve_schedule(members, tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"

    task_api = result["tasks"]["task-api"]
    task_ui = result["tasks"]["task-ui"]

    # task-ui は task-api に依存
    assert task_api["end_date"] < task_ui["start_date"]

    # 総工期 (Makespan): task-api (16h = 2日: 9/1, 9/2) + task-ui (24h = 3日: 9/3, 9/4, 9/7 [土日スキップ])
    # したがって Makespan は 5 稼働日
    assert result["makespan_workdays"] == 5


def test_scenario_4_output_schema(basic_data):
    """シナリオ 4: 開始日、終了日、担当メンバ、日ごとの割当工数が出力されること."""
    members, tasks, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    result = solve_schedule(members, tasks, calendar, start_date)

    assert result["status"] == "OPTIMAL"
    assert result["project_start_date"] == "2026-09-01"
    assert isinstance(result["makespan_workdays"], int)
    assert "tasks" in result
    assert "member_daily_work" in result
    assert "diagnostics" in result

    for t_id in ["task-api", "task-ui"]:
        t_info = result["tasks"][t_id]
        assert t_info["assigned_to"] in ["alice", "bob"]
        assert isinstance(t_info["start_date"], str)
        assert isinstance(t_info["end_date"], str)
        assert t_info["workdays_count"] > 0
        assert isinstance(t_info["estimate_hours"], float)
        assert isinstance(t_info["daily_hours"], dict)
        assert len(t_info["daily_hours"]) > 0

        # 合計日別時間が estimate_hours と一致すること
        total_daily = sum(t_info["daily_hours"].values())
        assert pytest.approx(total_daily, 0.01) == t_info["estimate_hours"]


def test_rounding_preserves_hours(basic_data):
    """0.1h 単位への丸め処理で round() を使用し、工数を失わないこと."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    custom_tasks = [
        {
            "id": "task-rounding",
            "title": "丸めテストタスク",
            "estimate_hours": 2.69,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]

    result = solve_schedule(members, custom_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-rounding"]
    total_hours = sum(t_info["daily_hours"].values())
    assert pytest.approx(total_hours, 0.01) == 2.7


    # max_capacity: 0.333 (0.333 * 8 = 2.664h -> 2.7h) と estimate_hours: 2.7 の組み合わせ
    custom_members = [
        {
            "id": "charlie",
            "name": "Charlie",
            "max_capacity": 0.333,
            "skills": ["backend"],
        }
    ]
    custom_tasks_2 = [
        {
            "id": "task-fit",
            "title": "ぴったり収まるタスク",
            "estimate_hours": 2.7,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]
    result2 = solve_schedule(custom_members, custom_tasks_2, calendar, start_date)
    assert result2["status"] == "OPTIMAL"
    assert result2["tasks"]["task-fit"]["workdays_count"] == 1
    assert result2["tasks"]["task-fit"]["daily_hours"]["2026-09-01"] == 2.7


def test_undefined_dependency_raises_error(basic_data):
    """未定義の先行タスクが指定された場合、ValueError を送出すること (FR-10)."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    invalid_tasks = [
        {
            "id": "task-valid",
            "title": "タスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": ["non-existent-task"],
        }
    ]

    with pytest.raises(ValueError, match="先行タスク 'non-existent-task' が tasks に定義されていません"):
        solve_schedule(members, invalid_tasks, calendar, start_date)


def test_large_workload_dynamic_horizon(basic_data):
    """30稼働日を超える大きなタスクでも、計画地平が自動拡張されて OPTIMAL で解けること (FR-11)."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    large_tasks = [
        {
            "id": "task-huge",
            "title": "大規模タスク",
            "estimate_hours": 248.0,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]

    result = solve_schedule(members, large_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    assert result["makespan_workdays"] == 31
    assert result["tasks"]["task-huge"]["workdays_count"] == 31


def test_past_deadline_handled_as_delay(basic_data):
    """開始日前の納期が正確に遅延として検知され、診断情報に記録されること."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    custom_tasks = [
        {
            "id": "task-past-deadline",
            "title": "開始前納期タスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-08-01",
        }
    ]

    result = solve_schedule(members, custom_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-past-deadline"]
    assert t_info["delay_days"] > 0
    assert result["diagnostics"]["is_deadline_violated"] is True
    assert len(result["diagnostics"]["delayed_tasks"]) == 1


def test_extremely_past_deadline_handled_without_infeasible(basic_data):
    """極端に古い過去の納期（例: 2020-01-01）でも INFEASIBLE にならず、動的な遅延上限により OPTIMAL で解けること."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    ancient_deadline_tasks = [
        {
            "id": "task-ancient-deadline",
            "title": "大昔の納期タスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2020-01-01",
        }
    ]

    result = solve_schedule(members, ancient_deadline_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-ancient-deadline"]
    assert t_info["delay_days"] > 1000
    assert result["diagnostics"]["is_deadline_violated"] is True
    assert result["diagnostics"]["delayed_tasks"][0]["task_id"] == "task-ancient-deadline"

