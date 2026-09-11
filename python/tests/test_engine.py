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
    """0.1h 刻みの工数で入力工数・出力工数・日別合計が完全に一致すること."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    custom_tasks = [
        {
            "id": "task-rounding",
            "title": "0.1h刻みテストタスク",
            "estimate_hours": 2.7,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]

    result = solve_schedule(members, custom_tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-rounding"]
    total_hours = sum(t_info["daily_hours"].values())
    assert pytest.approx(total_hours, 0.01) == 2.7
    # 入力工数と出力工数・日別合計が完全一致すること (R1)
    assert t_info["estimate_hours"] == 2.7
    assert pytest.approx(total_hours, 0.01) == t_info["estimate_hours"]

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


def test_invalid_step_or_sub_point_one_hours_raises_error(basic_data):
    """0.1時間未満 (0.04h, 0.05h) および 0.1h 刻みでない工数 (0.14h, 0.06h, 2.69h) で ValueError を送出すること (R1)."""
    members, _, calendar = basic_data
    start_date = datetime.date(2026, 9, 1)

    for invalid_hour in [0.04, 0.05, 0.06, 0.14, 2.69]:
        tasks = [
            {
                "id": "task-invalid-step",
                "title": f"不正工数タスク {invalid_hour}h",
                "estimate_hours": invalid_hour,
                "required_skills": ["backend"],
                "depends_on": [],
            }
        ]
        with pytest.raises(ValueError, match="0.1h 以上の 0.1h 刻み"):
            solve_schedule(members, tasks, calendar, start_date)


def test_non_workday_start_deadline_delay_detected(basic_data):
    """開始日が非稼働日で、納期が初稼働日より前にある場合、遅延が誤検知されず正しく検知されること (R2)."""
    members, _, calendar = basic_data
    # 2026-09-05 は土曜日、月〜金稼働なので最初の稼働日は 2026-09-07 (月)
    start_date = datetime.date(2026, 9, 5)

    # 納期を 2026-09-06 (日) に設定 (工数 8h なので月曜日に完了し、1稼働日遅延する)
    tasks = [
        {
            "id": "task-weekend",
            "title": "週末開始タスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-06",
        }
    ]

    result = solve_schedule(members, tasks, calendar, start_date)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-weekend"]

    # 2026-09-07 (月) に完了
    assert t_info["end_date"] == "2026-09-07"
    # 直前の稼働日は 2026-09-04 (金) のため、月曜完了は 1 稼働日遅延
    assert t_info["delay_days"] == 1
    assert result["diagnostics"]["is_deadline_violated"] is True
    assert len(result["diagnostics"]["delayed_tasks"]) == 1
    assert result["diagnostics"]["delayed_tasks"][0]["delay_workdays"] == 1


def test_empty_workdays_raises_error(basic_data):
    """calendar.workdays が空の場合、無限ループせず ValueError を送出すること (R3)."""
    members, tasks, _ = basic_data
    start_date = datetime.date(2026, 9, 1)

    empty_cal = {
        "workdays": [],
        "holidays": [],
    }

    with pytest.raises(ValueError, match="calendar.workdays に有効な稼働曜日が指定されていません"):
        solve_schedule(members, tasks, empty_cal, start_date)


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


# ==============================================================================
# Issue #13: チームカレンダー（祝日・非稼働日）を考慮した実稼働日スケジュール計算
# ==============================================================================


def test_scenario_issue13_ac1_non_workdays_skipped(basic_data):
    """AC-1: 週の非稼働日（デフォルト土日、または workdays 外の曜日）には工数が割り当てられないこと."""
    members, _, calendar = basic_data

    # 1. デフォルト土日スキップ検証 (金曜開始の16hタスク)
    friday_start = datetime.date(2026, 9, 4)  # 金曜日
    task_span_weekend = [
        {
            "id": "task-weekend-skip",
            "title": "週末スキップタスク",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]
    res1 = solve_schedule(members, task_span_weekend, calendar, friday_start)
    assert res1["status"] == "OPTIMAL"
    t1 = res1["tasks"]["task-weekend-skip"]
    assert t1["start_date"] == "2026-09-04"  # 金
    assert t1["end_date"] == "2026-09-07"    # 月
    assert "2026-09-05" not in t1["daily_hours"]  # 土
    assert "2026-09-06" not in t1["daily_hours"]  # 日
    assert t1["daily_hours"]["2026-09-04"] == 8.0
    assert t1["daily_hours"]["2026-09-07"] == 8.0

    # 2. カスタム稼働日（月・水・金のみ稼働）の検証
    custom_calendar = {
        "workdays": ["mon", "wed", "fri"],
        "holidays": [],
    }
    mon_start = datetime.date(2026, 9, 7)  # 月曜日
    res2 = solve_schedule(members, task_span_weekend, custom_calendar, mon_start)
    assert res2["status"] == "OPTIMAL"
    t2 = res2["tasks"]["task-weekend-skip"]
    assert t2["start_date"] == "2026-09-07"  # 月
    assert t2["end_date"] == "2026-09-09"    # 水 (火曜日は非稼働のためスキップ)
    assert "2026-09-08" not in t2["daily_hours"]  # 火 (非稼働日)
    assert t2["daily_hours"]["2026-09-07"] == 8.0
    assert t2["daily_hours"]["2026-09-09"] == 8.0

    # メンバ日別工数にも火曜日の割当が一切ないこと
    for m_id, days in res2["member_daily_work"].items():
        assert "2026-09-08" not in days


def test_scenario_issue13_ac2_holidays_skipped(basic_data):
    """AC-2: calendar.yaml に定義された祝日・特別休暇（holidays）には工数が割り当てられないこと."""
    members, _, calendar = basic_data

    # 1. basic calendar の祝日 2026-09-15 (火) スキップ検証
    mon_start = datetime.date(2026, 9, 14)  # 月曜日
    task_span_holiday = [
        {
            "id": "task-holiday-skip",
            "title": "祝日スキップタスク",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]
    res1 = solve_schedule(members, task_span_holiday, calendar, mon_start)
    assert res1["status"] == "OPTIMAL"
    t1 = res1["tasks"]["task-holiday-skip"]
    assert t1["start_date"] == "2026-09-14"  # 月
    assert t1["end_date"] == "2026-09-16"    # 水 (火曜日は祝日のためスキップ)
    assert "2026-09-15" not in t1["daily_hours"]  # 祝日
    assert t1["daily_hours"]["2026-09-14"] == 8.0
    assert t1["daily_hours"]["2026-09-16"] == 8.0

    # 2. PyYAML の非クォート日付 (datetime.date オブジェクト) および連続祝日
    consecutive_holidays_cal = {
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "holidays": [
            {"date": datetime.date(2026, 9, 21), "name": "敬老の日"},
            {"date": datetime.date(2026, 9, 22), "name": "国民の休日"},
        ],
    }
    fri_start = datetime.date(2026, 9, 18)  # 金曜日
    res2 = solve_schedule(members, task_span_holiday, consecutive_holidays_cal, fri_start)
    assert res2["status"] == "OPTIMAL"
    t2 = res2["tasks"]["task-holiday-skip"]
    # 金曜(9/18) -> 土(9/19)・日(9/20)・月(9/21祝)・火(9/22祝) をスキップ -> 水(9/23)
    assert t2["start_date"] == "2026-09-18"
    assert t2["end_date"] == "2026-09-23"
    assert "2026-09-21" not in t2["daily_hours"]
    assert "2026-09-22" not in t2["daily_hours"]


def test_scenario_issue13_ac3_span_across_weekend_and_holidays(basic_data):
    """AC-3: タスクが非稼働日（週末・祝日）を跨ぐ場合、実稼働日のみで所要見積工数が満たされるように期間が自動延長されること."""
    members, _, calendar = basic_data

    # 金曜開始、24h (3稼働日)、火曜 2026-09-15 が祝日
    fri_start = datetime.date(2026, 9, 11)  # 金曜日
    task_long = [
        {
            "id": "task-spanning",
            "title": "週末と祝日を跨ぐ3日タスク",
            "estimate_hours": 24.0,
            "required_skills": ["backend"],
            "depends_on": [],
        }
    ]

    result = solve_schedule(members, task_long, calendar, fri_start)
    assert result["status"] == "OPTIMAL"
    t_info = result["tasks"]["task-spanning"]

    # 稼働日は 金(9/11), 月(9/14), 水(9/16) の3日間
    # スキップ: 土(9/12), 日(9/13), 火(9/15祝)
    assert t_info["start_date"] == "2026-09-11"
    assert t_info["end_date"] == "2026-09-16"
    assert t_info["workdays_count"] == 3
    assert t_info["estimate_hours"] == 24.0
    assert t_info["daily_hours"] == {
        "2026-09-11": 8.0,
        "2026-09-14": 8.0,
        "2026-09-16": 8.0,
    }

    # カレンダー期間は 2026-09-11 から 2026-09-16 までの計 6 日間に自動延長されていること
    start_d = datetime.date.fromisoformat(t_info["start_date"])
    end_d = datetime.date.fromisoformat(t_info["end_date"])
    calendar_days_span = (end_d - start_d).days + 1
    assert calendar_days_span == 6


def test_scenario_issue13_ac4_iso_date_output_and_non_workday_project_start(basic_data):
    """AC-4: スケジュール結果の開始日・終了日が正確な実カレンダー日付（YYYY-MM-DD）で出力されること."""
    members, tasks, calendar = basic_data

    # 1. 週末（土曜日: 2026-09-12）を開始日に指定した場合
    sat_start = "2026-09-12"
    res_sat = solve_schedule(members, tasks, calendar, sat_start)
    assert res_sat["status"] == "OPTIMAL"
    assert res_sat["project_start_date"] == "2026-09-12"

    # 先頭タスクの開始日は土日をスキップした最初の実稼働日（2026-09-14 月曜日）であること
    first_task = res_sat["tasks"]["task-api"]
    assert first_task["start_date"] == "2026-09-14"

    # 2. 祝日（2026-09-15 火曜日）を開始日に指定した場合
    holiday_start = "2026-09-15"
    res_hol = solve_schedule(members, tasks, calendar, holiday_start)
    assert res_hol["status"] == "OPTIMAL"
    assert res_hol["project_start_date"] == "2026-09-15"

    # 先頭タスクの開始日は祝日をスキップした最初の実稼働日（2026-09-16 水曜日）であること
    first_task_hol = res_hol["tasks"]["task-api"]
    assert first_task_hol["start_date"] == "2026-09-16"

    # 3. deadline に datetime.date オブジェクト（非クォート YAML 想定）が渡された場合
    custom_tasks_date_obj = [
        {
            "id": "task-date-deadline",
            "title": "date型納期タスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": datetime.date(2026, 9, 30),
        }
    ]
    res_deadline = solve_schedule(members, custom_tasks_date_obj, calendar, "2026-09-01")
    assert res_deadline["status"] == "OPTIMAL"
    t_deadline = res_deadline["tasks"]["task-date-deadline"]
    assert isinstance(t_deadline["deadline"], str)
    assert t_deadline["deadline"] == "2026-09-30"
    assert isinstance(t_deadline["start_date"], str)
    assert isinstance(t_deadline["end_date"], str)


def test_missing_holiday_date_raises_error(basic_data):
    """calendar.holidays の項目に date が欠落している場合、ValueError を送出すること (R2)."""
    members, tasks, _ = basic_data
    start_date = datetime.date(2026, 9, 1)
    invalid_cal = {
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "holidays": [{"name": "missing date"}],
    }
    with pytest.raises(ValueError, match="calendar.holidays の各項目には 'date' フィールドが必須です"):
        solve_schedule(members, tasks, invalid_cal, start_date)


# ==============================================================================
# Issue #14: タスクの必須スキルを持つメンバのみにタスクを自動割り当てできる
# ==============================================================================


def test_scenario_issue14_ac1_single_and_multiple_required_skills(basic_data):
    """AC-1: required_skills が指定されたタスクは、該当スキルを保有するメンバにのみ割り当てられること (単一・複数スキル)."""
    members, _, calendar = basic_data
    # Alice: [frontend, backend], Bob: [backend, devops]
    start_date = datetime.date(2026, 9, 1)

    custom_tasks = [
        {
            "id": "task-single-skill",
            "title": "フロントエンド単一スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": ["frontend"],
            "depends_on": [],
        },
        {
            "id": "task-multi-skills",
            "title": "バックエンド＋インフラ複数スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": ["backend", "devops"],
            "depends_on": [],
        },
    ]

    res = solve_schedule(members, custom_tasks, calendar, start_date)
    assert res["status"] == "OPTIMAL"

    # task-single-skill は frontend を持つ Alice にのみ割り当て可能
    assert res["tasks"]["task-single-skill"]["assigned_to"] == "alice"

    # task-multi-skills は backend と devops の双方を持つ Bob にのみ割り当て可能 (Alice は devops を持たない)
    assert res["tasks"]["task-multi-skills"]["assigned_to"] == "bob"


def test_scenario_issue14_ac2_multi_candidate_workload_distribution(basic_data):
    """AC-2: 該当スキルを持つメンバが複数存在する場合、稼働上限や工期最適化を考慮して並行配分されること."""
    members, _, calendar = basic_data
    # Alice (8h/日) と Bob (6.4h/日) の双方が backend スキルを保有
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    custom_tasks = [
        {
            "id": "task-backend-1",
            "title": "バックエンドタスク1",
            "estimate_hours": 8.0,
            "required_skills": ["backend"],
            "depends_on": [],
        },
        {
            "id": "task-backend-2",
            "title": "バックエンドタスク2",
            "estimate_hours": 6.4,
            "required_skills": ["backend"],
            "depends_on": [],
        },
    ]

    res = solve_schedule(members, custom_tasks, calendar, start_date)
    assert res["status"] == "OPTIMAL"

    assigned_1 = res["tasks"]["task-backend-1"]["assigned_to"]
    assigned_2 = res["tasks"]["task-backend-2"]["assigned_to"]

    # 1人に集中させず、2人に分散して並行実行されていること
    assert {assigned_1, assigned_2} == {"alice", "bob"}

    # 並行実行されるため総工期 (Makespan) は 1 稼働日となること
    assert res["makespan_workdays"] == 1
    assert res["tasks"]["task-backend-1"]["start_date"] == "2026-09-01"
    assert res["tasks"]["task-backend-2"]["start_date"] == "2026-09-01"


def test_scenario_issue14_ac3_empty_or_omitted_required_skills(basic_data):
    """AC-3: required_skills が空または未指定のタスクは全メンバが担当候補となり、最適に配分されること."""
    members, _, calendar = basic_data
    # Alice: max_capacity 1.0 (8h/日), Bob: max_capacity 0.8 (6.4h/日)
    start_date = datetime.date(2026, 9, 1)

    # 1. 独立した2つのスキル制約なしタスク（空配列と未指定）が両メンバに並行配分されること
    # (片方に限定されていれば sequential に 2日かかるが、全メンバ候補なら並行配分され Makespan 1日になる)
    custom_tasks = [
        {
            "id": "task-empty-skills",
            "title": "空配列スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": [],
            "depends_on": [],
        },
        {
            "id": "task-omitted-skills",
            "title": "未指定スキルタスク",
            "estimate_hours": 6.4,
            "depends_on": [],
        },
    ]

    res = solve_schedule(members, custom_tasks, calendar, start_date)
    assert res["status"] == "OPTIMAL"

    assigned_empty = res["tasks"]["task-empty-skills"]["assigned_to"]
    assigned_omitted = res["tasks"]["task-omitted-skills"]["assigned_to"]
    # 両メンバに分散して割り当てられていること（特定メンバに偏らない）
    assert {assigned_empty, assigned_omitted} == {"alice", "bob"}
    assert res["makespan_workdays"] == 1
    assert res["tasks"]["task-empty-skills"]["start_date"] == "2026-09-01"
    assert res["tasks"]["task-omitted-skills"]["start_date"] == "2026-09-01"

    # 2. Alice 限定タスクが存在するとき、スキル空タスクが Bob に割り当てられること (Bob が候補であることを直接証明)
    tasks_alice_busy = [
        {
            "id": "task-frontend-only",
            "title": "Alice専用タスク",
            "estimate_hours": 8.0,
            "required_skills": ["frontend"],
            "depends_on": [],
        },
        {
            "id": "task-open-to-bob",
            "title": "誰でもよいタスク",
            "estimate_hours": 6.4,
            "required_skills": [],
            "depends_on": [],
        },
    ]
    res2 = solve_schedule(members, tasks_alice_busy, calendar, start_date)
    assert res2["status"] == "OPTIMAL"
    assert res2["tasks"]["task-frontend-only"]["assigned_to"] == "alice"
    assert res2["tasks"]["task-open-to-bob"]["assigned_to"] == "bob"
    assert res2["makespan_workdays"] == 1

    # 3. Bob 限定タスクが存在するとき、未指定タスクが Alice に割り当てられること (Alice が候補であることを直接証明)
    tasks_bob_busy = [
        {
            "id": "task-devops-only",
            "title": "Bob専用タスク",
            "estimate_hours": 6.4,
            "required_skills": ["devops"],
            "depends_on": [],
        },
        {
            "id": "task-open-to-alice",
            "title": "未指定タスク",
            "estimate_hours": 8.0,
            "depends_on": [],
        },
    ]
    res3 = solve_schedule(members, tasks_bob_busy, calendar, start_date)
    assert res3["status"] == "OPTIMAL"
    assert res3["tasks"]["task-devops-only"]["assigned_to"] == "bob"
    assert res3["tasks"]["task-open-to-alice"]["assigned_to"] == "alice"
    assert res3["makespan_workdays"] == 1


def test_scenario_issue14_ac4_unfulfillable_skills_raises_error(basic_data):
    """AC-4: 必須スキルを充足するメンバがチーム内に不在の場合、および不正型の場合に ValueError を送出すること."""
    members, _, calendar = basic_data
    # Alice: [frontend, backend], Bob: [backend, devops]
    start_date = datetime.date(2026, 9, 1)

    # 1. チーム内の誰も持っていない未知のスキル
    task_unknown_skill = [
        {
            "id": "task-unknown",
            "title": "未知スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": ["machine-learning"],
            "depends_on": [],
        }
    ]
    with pytest.raises(ValueError, match="必須スキル.*保有するメンバが.*存在しません"):
        solve_schedule(members, task_unknown_skill, calendar, start_date)

    # 2. 個別スキルはチーム内に存在するが、単一メンバで全スキルを兼任できない組み合わせ
    # Alice lacks devops, Bob lacks frontend -> No member has both
    task_impossible_combo = [
        {
            "id": "task-impossible-combo",
            "title": "兼任不能スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": ["frontend", "devops"],
            "depends_on": [],
        }
    ]
    with pytest.raises(ValueError, match="必須スキル.*保有するメンバが.*存在しません"):
        solve_schedule(members, task_impossible_combo, calendar, start_date)

    # 3. 明示的な null は 001-yaml-schema と同様に拒否されること (R1)
    task_null_skills = [
        {
            "id": "task-null-skills",
            "title": "nullスキルタスク",
            "estimate_hours": 8.0,
            "required_skills": None,
            "depends_on": [],
        }
    ]
    with pytest.raises(ValueError, match="required_skills.*null は不可"):
        solve_schedule(members, task_null_skills, calendar, start_date)

    # 4. 配列以外の不正な型（文字列など）が指定された場合も ValueError となること
    task_invalid_type_skills = [
        {
            "id": "task-invalid-type",
            "title": "型不正スキルタスク",
            "estimate_hours": 8.0,
            "required_skills": "backend",
            "depends_on": [],
        }
    ]
    with pytest.raises(ValueError, match="required_skills は文字列のリストである必要があります"):
        solve_schedule(members, task_invalid_type_skills, calendar, start_date)


# ==============================================================================
# Issue #15: 納期制約の充足判定と制約充足不能（Infeasible）時のボトルネック診断
# ==============================================================================


def test_scenario_issue15_ac1_deadline_met_no_delay(basic_data):
    """AC-1: deadline が指定され、期限内完了可能な場合に delay_days: 0 で計画されること."""
    members, _, calendar = basic_data
    # Alice (8h/日) のみを使用
    alice_only = [m for m in members if m["id"] == "alice"]
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    tasks = [
        {
            "id": "task-api",
            "title": "API実装",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-02",  # 2稼働日目の終了時 (9/1, 9/2 で完了可能)
        },
        {
            "id": "task-ui",
            "title": "UI実装",
            "estimate_hours": 24.0,
            "required_skills": ["frontend"],
            "depends_on": ["task-api"],
            "deadline": "2026-09-10",  # 9/7完了予定なので余裕あり
        },
    ]

    res = solve_schedule(alice_only, tasks, calendar, start_date)
    assert res["status"] == "OPTIMAL"

    # task-api は 2026-09-02 に完了し遅延なし
    assert res["tasks"]["task-api"]["end_date"] == "2026-09-02"
    assert res["tasks"]["task-api"]["delay_days"] == 0

    # task-ui は 2026-09-07 に完了し遅延なし
    assert res["tasks"]["task-ui"]["end_date"] == "2026-09-07"
    assert res["tasks"]["task-ui"]["delay_days"] == 0

    # 診断結果に遅延フラグが false で集計が 0 であること
    assert res["diagnostics"]["is_deadline_violated"] is False
    assert res["diagnostics"]["total_delay_workdays"] == 0
    assert res["diagnostics"]["delayed_tasks"] == []
    assert res["diagnostics"]["recommendations"] == []


def test_scenario_issue15_ac2_infeasible_detected_without_crash(basic_data):
    """AC-2: 期限内完了が不可能な場合（制約充足不能）、例外でクラッシュせず結果ステータスと遅延情報を返すこと."""
    members, _, calendar = basic_data
    alice_only = [m for m in members if m["id"] == "alice"]
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    # 合計 40h (5稼働日分) のタスクに対して、後続の deadline が 2稼働日目 (2026-09-02) に設定
    tasks = [
        {
            "id": "task-api",
            "title": "API実装",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-02",
        },
        {
            "id": "task-ui",
            "title": "UI実装",
            "estimate_hours": 24.0,
            "required_skills": ["frontend"],
            "depends_on": ["task-api"],
            "deadline": "2026-09-02",  # 先行タスク完了日と同じ日に設定（先行タスクがあるため達成不可能）
        },
    ]

    # 例外でクラッシュせずに正常終了すること
    res = solve_schedule(alice_only, tasks, calendar, start_date)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")

    # 診断情報で納期違反が検知されていること
    assert res["diagnostics"]["is_deadline_violated"] is True
    assert len(res["diagnostics"]["delayed_tasks"]) >= 1
    delayed_ids = [d["task_id"] for d in res["diagnostics"]["delayed_tasks"]]
    assert "task-ui" in delayed_ids


def test_scenario_issue15_ac3_bottleneck_diagnosis_report(basic_data):
    """AC-3: 充足不能となった原因（先行タスク待ち、日別稼働上限など）のボトルネック診断レポートが出力されること."""
    members, _, calendar = basic_data
    alice_only = [m for m in members if m["id"] == "alice"]
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    # 先行タスク task-api (16h = 2日) -> 後続タスク task-ui (24h = 3日)
    # task-ui の deadline を 2026-09-02 に設定
    # 理由: 先行タスク task-api の完了 (2026-09-02) 待ちにより、後続タスクは最短でも 2026-09-03 着手となり納期に間に合わない
    tasks = [
        {
            "id": "task-api",
            "title": "API実装",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-02",
        },
        {
            "id": "task-ui",
            "title": "UI実装",
            "estimate_hours": 24.0,
            "required_skills": ["frontend"],
            "depends_on": ["task-api"],
            "deadline": "2026-09-02",
        },
    ]

    res = solve_schedule(alice_only, tasks, calendar, start_date)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")

    diag_tasks = {d["task_id"]: d for d in res["diagnostics"]["delayed_tasks"]}
    assert "task-ui" in diag_tasks
    ui_diag = diag_tasks["task-ui"]

    assert ui_diag["delay_workdays"] == 3
    assert ui_diag["deadline"] == "2026-09-02"
    assert ui_diag["projected_end_date"] == "2026-09-07"
    # reason に先行タスク task-api の待ちまたは稼働上限への言及が含まれること
    assert "task-api" in ui_diag["reason"] or "先行タスク" in ui_diag["reason"]


def test_scenario_issue15_ac4_summary_and_recommendations(basic_data):
    """AC-4: 超過日数サマリー (total_delay_workdays) と推奨緩和情報 (recommendations) が提示されること."""
    members, _, calendar = basic_data
    alice_only = [m for m in members if m["id"] == "alice"]
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    tasks = [
        {
            "id": "task-api",
            "title": "API実装",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-02",
        },
        {
            "id": "task-ui",
            "title": "UI実装",
            "estimate_hours": 24.0,
            "required_skills": ["frontend"],
            "depends_on": ["task-api"],
            "deadline": "2026-09-02",
        },
    ]

    res = solve_schedule(alice_only, tasks, calendar, start_date)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")

    diagnostics = res["diagnostics"]
    assert diagnostics["is_deadline_violated"] is True
    assert diagnostics["total_delay_workdays"] == 3

    recs = diagnostics["recommendations"]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["task_id"] == "task-ui"
    assert rec["action"] == "extend_deadline"
    assert rec["recommended_deadline"] == "2026-09-07"
    assert rec["additional_workdays_needed"] == 3


def test_scenario_issue15_multiple_delayed_tasks(basic_data):
    """複数タスクが同時に納期遅延する場合、全タスクの超過日数と緩和推奨が正確に出力されること."""
    members, _, calendar = basic_data
    alice_only = [m for m in members if m["id"] == "alice"]
    start_date = datetime.date(2026, 9, 1)  # 火曜日

    # 独立した2つの16hタスク（Alice 1人なので sequential に 2日 + 2日 = 4稼働日必要）
    # どちらも deadline: 2026-09-01 (1稼働日目)
    tasks = [
        {
            "id": "task-1",
            "title": "タスク1",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-01",
        },
        {
            "id": "task-2",
            "title": "タスク2",
            "estimate_hours": 16.0,
            "required_skills": ["backend"],
            "depends_on": [],
            "deadline": "2026-09-01",
        },
    ]

    res = solve_schedule(alice_only, tasks, calendar, start_date)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")

    diagnostics = res["diagnostics"]
    assert diagnostics["is_deadline_violated"] is True
    delayed_ids = {d["task_id"] for d in diagnostics["delayed_tasks"]}
    assert delayed_ids == {"task-1", "task-2"}

    # 1つは2日目 (9/2) に完了 -> 1日遅延
    # もう1つは4日目 (9/4) に完了 -> 3日遅延
    # 合計遅延日数 = 1 + 3 = 4稼働日
    assert diagnostics["total_delay_workdays"] == 4

    rec_ids = {r["task_id"] for r in diagnostics["recommendations"]}
    assert rec_ids == {"task-1", "task-2"}


