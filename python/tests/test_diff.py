"""スケジュール差分算出と再計画遅延原因診断の単体テスト.

仕様書: specs/004-actuals-and-replanning.md
受入基準:
- AC-1: ベースラインと再計画スケジュールの差分算出 (Makespan, 開始日・終了日・稼働日数スリップ)
- AC-2: 再計画遅延原因の診断 (工数増大, メンバ欠勤, 先行タスク遅延)
- AC-3: 納期超過タスクに対する推奨納期緩和日 (Recommendations)
- AC-4: Python API (taskweave.diff, taskweave.replan) の動作
"""

import datetime
from pathlib import Path
import pytest

from taskweave.diff import compute_schedule_diff, format_diff_summary
from taskweave.engine import replan, solve_schedule


@pytest.fixture
def base_members():
    return [
        {"id": "alice", "name": "Alice", "skills": ["python"], "max_capacity": 1.0},
        {"id": "bob", "name": "Bob", "skills": ["frontend", "python"], "max_capacity": 1.0},
    ]


@pytest.fixture
def base_calendar():
    return {
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
        "holidays": [],
        "absences": [],
    }


class TestScheduleDiffAC1:
    """AC-1: ベースラインと再計画スケジュールの差分算出."""

    def test_diff_ac1_makespan_and_task_slips(self, base_members, base_calendar):
        tasks = [
            {"id": "t1", "title": "Task 1", "estimate_hours": 8.0, "required_skills": ["python"]},
            {"id": "t2", "title": "Task 2", "estimate_hours": 8.0, "required_skills": ["python"], "depends_on": ["t1"]},
        ]
        start_date = "2026-09-07"  # Mon

        # ベースライン (実績なし)
        baseline = solve_schedule(base_members, tasks, base_calendar, start_date)

        # 再計画 (t1 に工数超過があり、t1 と t2 が後ろ倒しになるシナリオ)
        actuals = {
            "work_logs": [
                {"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 8.0},
            ],
            "task_progress": [
                {"task_id": "t1", "remaining_hours": 8.0, "status": "in_progress"},  # 計16h (+8h)
            ],
        }
        replanned = solve_schedule(base_members, tasks, base_calendar, start_date, as_of_date="2026-09-08", actuals_data=actuals)

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=base_calendar)

        # Makespan 差分検証
        assert diff["makespan"]["baseline_workdays"] == 2
        assert diff["makespan"]["replanned_workdays"] == 3
        assert diff["makespan"]["slip_workdays"] == 1

        # タスク t1 差分検証
        t1_diff = diff["tasks"]["t1"]["diff"]
        assert t1_diff["end_date_slip_days"] == 1  # 2026-09-07 -> 2026-09-08
        assert t1_diff["workdays_count_diff"] == 1  # 1日 -> 2日
        assert not t1_diff["assignee_changed"]

        # タスク t2 差分検証
        t2_diff = diff["tasks"]["t2"]["diff"]
        assert t2_diff["start_date_slip_days"] == 1  # 2026-09-08 -> 2026-09-09
        assert t2_diff["end_date_slip_days"] == 1


class TestScheduleDiffAC2Diagnostics:
    """AC-2: 再計画遅延原因の診断 (工数増大, メンバ欠勤, 先行タスク遅延)."""

    def test_diff_ac2_workload_increase(self, base_members, base_calendar):
        tasks = [
            {"id": "t1", "title": "API", "estimate_hours": 8.0, "required_skills": ["python"]},
        ]
        start_date = "2026-09-07"
        baseline = solve_schedule(base_members, tasks, base_calendar, start_date)

        actuals = {
            "work_logs": [{"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 6.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 6.0, "status": "in_progress"}],  # 計12h
        }
        replanned = solve_schedule(base_members, tasks, base_calendar, start_date, as_of_date="2026-09-08", actuals_data=actuals)

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=base_calendar)
        t1_diag = diff["tasks"]["t1"]["diagnostics"]

        assert t1_diag["is_delayed"] is True
        assert t1_diag["primary_reason"] == "workload_increase"
        assert "workload_increase" in t1_diag["reasons"]
        assert any("超過" in d or "工数" in d for d in t1_diag["details"])

    def test_diff_ac2_member_absence(self, base_members):
        # Alice のみ担当可能なタスクで、Alice が不在
        members = [
            {"id": "alice", "name": "Alice", "skills": ["python"], "max_capacity": 1.0},
        ]
        tasks = [
            {"id": "t1", "title": "Task 1", "estimate_hours": 16.0, "required_skills": ["python"]},
        ]
        start_date = "2026-09-07"  # Mon: 09-07, 09-08 で完了予定
        baseline = solve_schedule(members, tasks, {"workdays": ["mon", "tue", "wed", "thu", "fri"]}, start_date)

        # 09-08 に Alice が突発不在
        calendar_with_absence = {
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "absences": [{"member_id": "alice", "date": "2026-09-08", "name": "体調不良"}],
        }
        actuals = {
            "work_logs": [{"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 8.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 8.0, "status": "in_progress"}],  # 工数増減なし
        }
        replanned = solve_schedule(
            members, tasks, calendar_with_absence, start_date, as_of_date="2026-09-08", actuals_data=actuals
        )

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=calendar_with_absence)
        t1_diag = diff["tasks"]["t1"]["diagnostics"]

        assert t1_diag["is_delayed"] is True
        assert t1_diag["primary_reason"] == "member_absence"
        assert "member_absence" in t1_diag["reasons"]
        assert any("不在" in d for d in t1_diag["details"])

    def test_diff_ac2_dependency_delay(self, base_members, base_calendar):
        tasks = [
            {"id": "t1", "title": "Task 1", "estimate_hours": 8.0, "required_skills": ["python"]},
            {"id": "t2", "title": "Task 2", "estimate_hours": 8.0, "required_skills": ["python"], "depends_on": ["t1"]},
        ]
        start_date = "2026-09-07"
        baseline = solve_schedule(base_members, tasks, base_calendar, start_date)

        # t1 の工数増大により t2 が後ろ倒しになる
        actuals = {
            "work_logs": [{"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 8.0}],
            "task_progress": [
                {"task_id": "t1", "remaining_hours": 8.0, "status": "in_progress"},
                {"task_id": "t2", "remaining_hours": 8.0, "status": "not_started"},  # t2 自身は工数増大なし
            ],
        }
        replanned = solve_schedule(base_members, tasks, base_calendar, start_date, as_of_date="2026-09-08", actuals_data=actuals)

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=base_calendar)
        t2_diag = diff["tasks"]["t2"]["diagnostics"]

        assert t2_diag["is_delayed"] is True
        assert t2_diag["primary_reason"] == "dependency_delay"
        assert "dependency_delay" in t2_diag["reasons"]
        assert any("t1" in d for d in t2_diag["details"])


class TestScheduleDiffAC3Recommendations:
    """AC-3: 納期超過タスクに対する推奨納期緩和日."""

    def test_recommendation_for_delayed_deadline_task(self, base_members, base_calendar):
        tasks = [
            {"id": "t1", "title": "API", "estimate_hours": 8.0, "required_skills": ["python"], "deadline": "2026-09-07"},
        ]
        start_date = "2026-09-07"
        baseline = solve_schedule(base_members, tasks, base_calendar, start_date)

        actuals = {
            "work_logs": [{"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 8.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 8.0, "status": "in_progress"}],  # 2026-09-08 完了に延伸
        }
        replanned = solve_schedule(base_members, tasks, base_calendar, start_date, as_of_date="2026-09-08", actuals_data=actuals)

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=base_calendar)
        recs = diff["recommendations"]

        assert len(recs) == 1
        assert recs[0]["task_id"] == "t1"
        assert recs[0]["current_deadline"] == "2026-09-07"
        assert recs[0]["recommended_deadline"] == "2026-09-08"
        assert recs[0]["delay_days"] == 1
        assert "緩和" in recs[0]["message"]


class TestScheduleDiffAC4API:
    """AC-4: Python API (taskweave.diff, taskweave.replan) の動作."""

    def test_replan_api_from_directory(self, tmp_path: Path):
        # サンプル原本 YAML を配置
        (tmp_path / "members.yaml").write_text(
            """members:
  - id: alice
    name: Alice
    skills: [backend]
    max_capacity: 1.0
""",
            encoding="utf-8",
        )
        (tmp_path / "calendar.yaml").write_text(
            """calendar:
  workdays: [mon, tue, wed, thu, fri]
  holidays: []
""",
            encoding="utf-8",
        )
        (tmp_path / "tasks.yaml").write_text(
            """tasks:
  - id: t1
    title: Task 1
    estimate_hours: 8.0
    required_skills: [backend]
""",
            encoding="utf-8",
        )
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-07'
    member_id: alice
    task_id: t1
    hours: 8.0
task_progress:
  - task_id: t1
    remaining_hours: 8.0
    status: in_progress
""",
            encoding="utf-8",
        )

        result = replan(data_dir=tmp_path, as_of_date="2026-09-08", project_start_date="2026-09-07")
        assert "baseline" in result
        assert "replanned" in result
        assert "diff" in result
        assert result["diff"]["makespan"]["slip_workdays"] == 1

    def test_format_diff_summary(self, base_members, base_calendar):
        tasks = [
            {"id": "t1", "title": "Task 1", "estimate_hours": 8.0, "required_skills": ["python"]},
        ]
        start_date = "2026-09-07"
        baseline = solve_schedule(base_members, tasks, base_calendar, start_date)
        actuals = {
            "work_logs": [{"date": "2026-09-07", "member_id": "alice", "task_id": "t1", "hours": 8.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 8.0, "status": "in_progress"}],
        }
        replanned = solve_schedule(base_members, tasks, base_calendar, start_date, as_of_date="2026-09-08", actuals_data=actuals)

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks, calendar_data=base_calendar)
        text = format_diff_summary(diff)

        assert "Taskweave Replanning & Diff Report" in text
        assert "Makespan:" in text
        assert "t1" in text
        assert "workload_increase" in text or "工数増大" in text

    def test_diff_null_values_handling_r1(self):
        """[R1]: None (null) 値が含まれる辞書でもクラッシュせず正常に差分とサマリーが生成されること."""
        baseline = {
            "status": "OPTIMAL",
            "makespan_workdays": None,
            "tasks": {
                "t1": {
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-07",
                    "assigned_to": "alice",
                    "workdays_count": None,
                    "delay_days": None,
                }
            },
        }
        replanned = {
            "status": "OPTIMAL",
            "makespan_workdays": 3,
            "tasks": {
                "t1": {
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-09",
                    "assigned_to": "alice",
                    "workdays_count": None,
                    "delay_days": None,
                    "estimate_hours": None,
                    "remaining_hours": None,
                    "total_logged_hours": None,
                }
            },
        }

        diff = compute_schedule_diff(baseline, replanned)
        assert diff["makespan"]["baseline_workdays"] == 0
        assert diff["makespan"]["replanned_workdays"] == 3
        assert diff["tasks"]["t1"]["diff"]["end_date_slip_days"] == 2
        text = format_diff_summary(diff)
        assert "t1" in text

    def test_diff_deadline_fallback_to_tasks_data_r2(self):
        """[R2]: replanned に deadline が存在しない場合でも tasks_data の deadline をフォールバック利用すること."""
        baseline = {
            "status": "OPTIMAL",
            "makespan_workdays": 1,
            "tasks": {
                "t1": {
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-07",
                    "assigned_to": "alice",
                    "workdays_count": 1,
                    "delay_days": 0,
                }
            },
        }
        replanned = {
            "status": "OPTIMAL",
            "makespan_workdays": 2,
            "tasks": {
                "t1": {
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-08",
                    "assigned_to": "alice",
                    "workdays_count": 2,
                    "delay_days": 0,
                    # deadline は意図的に省略
                }
            },
        }
        tasks_data = [
            {"id": "t1", "title": "Task 1", "estimate_hours": 8.0, "deadline": "2026-09-07"},
        ]

        diff = compute_schedule_diff(baseline, replanned, tasks_data=tasks_data)
        assert len(diff["recommendations"]) == 1
        rec = diff["recommendations"][0]
        assert rec["task_id"] == "t1"
        assert rec["current_deadline"] == "2026-09-07"
        assert rec["recommended_deadline"] == "2026-09-08"

