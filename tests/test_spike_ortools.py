"""Spike OR-Tools スケジューリング計算エンジンの単体テスト.

検証項目:
1. 出力契約 (Output Schema / Contract)
2. 0.1h 単位への丸め処理 (round)
3. 開始日前の納期における遅延計算
4. 未定義の依存タスクに対する入力検証エラー (ValueError)
5. 計画地平の自動拡張 (30日超のタスクに対する INFEASIBLE 回避)
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest
import sys

# scripts/spikes を import パスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "spikes"))

from spike_ortools import count_workdays_between, load_yaml, solve_schedule


@pytest.fixture
def basic_data() -> tuple[list[dict], list[dict], dict]:
    data_dir = Path(__file__).resolve().parent.parent / "examples" / "basic"
    members = load_yaml(data_dir / "members.yaml")["members"]
    tasks = load_yaml(data_dir / "tasks.yaml")["tasks"]
    calendar = load_yaml(data_dir / "calendar.yaml")["calendar"]
    return members, tasks, calendar


def test_output_contract(basic_data):
    """出力辞書が specs/003-scheduling-engine.md の出力スキーマと一致すること."""
    members, tasks, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    result = solve_schedule(members, tasks, calendar, start_date)

    assert result["status"] == "OPTIMAL"
    assert result["project_start_date"] == "2026-09-01"
    assert result["makespan_workdays"] == 5
    assert "tasks" in result
    assert "member_daily_work" in result
    assert "diagnostics" in result

    # タスクごとの契約確認
    for t_id in ["task-api", "task-ui"]:
        t_info = result["tasks"][t_id]
        assert "assigned_to" in t_info
        assert "start_date" in t_info
        assert "end_date" in t_info
        assert "workdays_count" in t_info
        assert isinstance(t_info["estimate_hours"], float)
        assert isinstance(t_info["daily_hours"], dict)
        assert "deadline" in t_info
        assert "delay_days" in t_info

    # 診断結果の契約確認
    diagnostics = result["diagnostics"]
    assert diagnostics["is_deadline_violated"] is False
    assert diagnostics["delayed_tasks"] == []


def test_rounding_preserves_hours(basic_data):
    """0.1h 単位への丸め処理で round() を使用し、工数を失わないこと."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    # estimate_hours: 2.69 -> 2.7h に丸められること
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
    # 合計工数が 2.7h であること
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
    # 1日に収まること (workdays_count == 1)
    assert result2["tasks"]["task-fit"]["workdays_count"] == 1
    assert result2["tasks"]["task-fit"]["daily_hours"]["2026-09-01"] == 2.7


def test_past_deadline_handled_as_delay(basic_data):
    """開始日前の納期が正確に遅延として検知され、診断情報に記録されること."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    # 納期を開始日より前の 2026-08-01 に設定
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
    # 遅延日数が 0 ではなく正の値になること
    assert t_info["delay_days"] > 0

    # 診断結果に記録されていること
    diagnostics = result["diagnostics"]
    assert diagnostics["is_deadline_violated"] is True
    assert len(diagnostics["delayed_tasks"]) == 1
    delayed = diagnostics["delayed_tasks"][0]
    assert delayed["task_id"] == "task-past-deadline"
    assert delayed["delay_workdays"] == t_info["delay_days"]
    assert delayed["deadline"] == "2026-08-01"


def test_undefined_dependency_raises_error(basic_data):
    """未定義の先行タスクが指定された場合、ValueError を送出すること."""
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
    """30稼働日を超える大きなタスクでも、計画地平が自動拡張されて OPTIMAL で解けること."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    # 248 時間 (1.0 capacity = 8h/日 の場合、31 稼働日必要)
    large_tasks = [
        {
            "id": "task-huge",
            "title": "大規模タスク",
            "estimate_hours": 248.0,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]

    # horizon_days を明示せずデフォルト (None) で呼ぶ
    result = solve_schedule(members, large_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    assert result["makespan_workdays"] == 31
    assert result["tasks"]["task-huge"]["workdays_count"] == 31

