"""YAML 原本データおよび論理整合性バリデータのテスト.

仕様書: specs/001-yaml-schema.md
"""

from pathlib import Path
import pytest
from taskweave.validator import (
    resolve_task_progress,
    validate_actuals,
    validate_calendar,
    validate_logical_integrity,
    validate_members,
    validate_project_data,
    validate_schedule_inputs,
    validate_tasks,
)

BASIC_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "basic"


class TestSchemaValidation:
    """Scenario 1: 正常系原本データの読み込みと検証."""

    def test_members_yaml_success(self):
        content = (BASIC_DIR / "members.yaml").read_text(encoding="utf-8")
        result = validate_members(content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.data) == 2

        alice = result.data[0]
        assert alice["id"] == "alice"
        assert alice["name"] == "Alice"
        assert alice["max_capacity"] == 1.0
        assert alice["skills"] == ["frontend", "backend"]

        bob = result.data[1]
        assert bob["id"] == "bob"
        assert bob["max_capacity"] == 0.8
        assert bob["skills"] == ["backend", "devops"]

    def test_tasks_yaml_success(self):
        content = (BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8")
        result = validate_tasks(content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.data) == 2

        task_api = result.data[0]
        assert task_api["id"] == "task-api"
        assert task_api["estimate_hours"] == 16.0
        assert task_api["required_skills"] == ["backend"]
        assert task_api["depends_on"] == []
        assert task_api["deadline"] == "2026-09-20"

        task_ui = result.data[1]
        assert task_ui["id"] == "task-ui"
        assert task_ui["estimate_hours"] == 24.0
        assert task_ui["depends_on"] == ["task-api"]

    def test_calendar_yaml_success(self):
        content = (BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8")
        result = validate_calendar(content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.data["workdays"] == ["mon", "tue", "wed", "thu", "fri"]
        assert len(result.data["holidays"]) == 2
        assert result.data["holidays"][0]["date"] == "2026-09-15"
        assert result.data["holidays"][0]["name"] == "敬老の日"

    def test_validate_project_data_success(self):
        result = validate_project_data(BASIC_DIR)
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.members is not None
        assert result.tasks is not None
        assert result.calendar is not None


class TestRequiredFieldsMissing:
    """Scenario 2: 必須フィールド欠落時の検知."""

    def test_missing_member_id(self):
        yaml_content = """
members:
  - name: "No ID Member"
"""
        result = validate_members(yaml_content)
        assert result.valid is False
        assert any("id" in err for err in result.errors)

    def test_missing_task_estimate_hours(self):
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task without estimate"
"""
        result = validate_tasks(yaml_content)
        assert result.valid is False
        assert any("estimate_hours" in err for err in result.errors)

    def test_missing_holiday_date(self):
        yaml_content = """
calendar:
  holidays:
    - name: "Holiday without date"
"""
        result = validate_calendar(yaml_content)
        assert result.valid is False
        assert any("date" in err for err in result.errors)


class TestInvalidTypesAndConstraints:
    """Scenario 3: 不正な型・制約違反の検知."""

    def test_invalid_max_capacity_range(self):
        yaml_over = """
members:
  - id: "m1"
    name: "Over"
    max_capacity: 1.5
"""
        assert validate_members(yaml_over).valid is False

        yaml_zero = """
members:
  - id: "m2"
    name: "Zero"
    max_capacity: 0.0
"""
        assert validate_members(yaml_zero).valid is False

    def test_invalid_estimate_hours(self):
        yaml_zero = """
tasks:
  - id: "t1"
    title: "Zero hours"
    estimate_hours: 0
"""
        assert validate_tasks(yaml_zero).valid is False

        yaml_string = """
tasks:
  - id: "t2"
    title: "String hours"
    estimate_hours: "five"
"""
        assert validate_tasks(yaml_string).valid is False

        yaml_sub = """
tasks:
  - id: "t3"
    title: "Too small 0.04"
    estimate_hours: 0.04
"""
        res_sub = validate_tasks(yaml_sub)
        assert res_sub.valid is False
        assert any("0.1 以上" in e for e in res_sub.errors)

        yaml_not_step = """
tasks:
  - id: "t5"
    title: "Non step 0.14"
    estimate_hours: 0.14
"""
        res_not_step = validate_tasks(yaml_not_step)
        assert res_not_step.valid is False
        assert any("0.1 時間刻み" in e for e in res_not_step.errors)

    def test_invalid_deadline_format(self):
        yaml_invalid_date = """
tasks:
  - id: "t1"
    title: "Invalid date"
    estimate_hours: 8
    deadline: "2026-02-30"
"""
        result = validate_tasks(yaml_invalid_date)
        assert result.valid is False
        assert any("deadline" in e for e in result.errors)

    def test_invalid_calendar_workdays(self):
        yaml_invalid = """
calendar:
  workdays: [mon, tue, funday]
"""
        result = validate_calendar(yaml_invalid)
        assert result.valid is False
        assert any("workdays" in e for e in result.errors)

        yaml_empty = """
calendar:
  workdays: []
"""
        res_empty = validate_calendar(yaml_empty)
        assert res_empty.valid is False
        assert any("少なくとも1つの有効な稼働曜日" in e for e in res_empty.errors)

    def test_duplicate_ids(self):
        yaml_dup = """
members:
  - id: "m1"
    name: "Member 1"
  - id: "m1"
    name: "Member 1 Duplicate"
"""
        result = validate_members(yaml_dup)
        assert result.valid is False
        assert any("重複" in e for e in result.errors)

    def test_invalid_and_duplicate_holidays(self):
        yaml_invalid_date = """
calendar:
  holidays:
    - date: "2026-02-30"
      name: "存在しない日"
"""
        assert validate_calendar(yaml_invalid_date).valid is False

        yaml_dup_date = """
calendar:
  holidays:
    - date: "2026-09-15"
      name: "敬老の日"
    - date: "2026-09-15"
      name: "重複した祝日"
"""
        res_dup = validate_calendar(yaml_dup_date)
        assert res_dup.valid is False
        assert any("重複" in e for e in res_dup.errors)

    def test_duplicate_workdays(self):
        yaml_dup = """
calendar:
  workdays: [mon, tue, mon]
"""
        res = validate_calendar(yaml_dup)
        assert res.valid is False
        assert any("重複" in e for e in res.errors)


class TestFeedbackAndEdgeCases:
    """PR Review Feedback Edge Cases."""

    def test_empty_or_whitespace_yaml(self):
        res1 = validate_members("")
        assert res1.valid is False
        assert len(res1.errors) > 0

        res2 = validate_tasks("   \n\n  ")
        assert res2.valid is False
        assert len(res2.errors) > 0

    def test_nan_and_inf_rejected(self):
        yaml_nan = """
members:
  - id: "m1"
    name: "Alice"
    max_capacity: .nan
"""
        assert validate_members(yaml_nan).valid is False

        yaml_inf = """
members:
  - id: "m2"
    name: "Bob"
    max_capacity: .inf
"""
        assert validate_members(yaml_inf).valid is False

        task_nan = """
tasks:
  - id: "t1"
    title: "NaN"
    estimate_hours: .nan
"""
        assert validate_tasks(task_nan).valid is False

    def test_calendar_as_list_rejected(self):
        res = validate_calendar("calendar: []")
        assert res.valid is False
        assert any("calendar" in e for e in res.errors)

    def test_holidays_name_type_invalid(self):
        yaml_num = """
calendar:
  holidays:
    - date: "2026-09-15"
      name: 123
"""
        assert validate_calendar(yaml_num).valid is False

        yaml_null = """
calendar:
  holidays:
    - date: "2026-09-15"
      name: null
"""
        assert validate_calendar(yaml_null).valid is False

    def test_explicit_null_rejected(self):
        yaml_cap_null = """
members:
  - id: "m1"
    name: "Alice"
    max_capacity: null
"""
        assert validate_members(yaml_cap_null).valid is False

        yaml_skills_null = """
members:
  - id: "m1"
    name: "Alice"
    skills: null
"""
        assert validate_members(yaml_skills_null).valid is False

        task_null = """
tasks:
  - id: "t1"
    title: "Task"
    estimate_hours: 8
    required_skills: null
    depends_on: null
"""
        res = validate_tasks(task_null)
        assert res.valid is False
        assert any("required_skills" in e for e in res.errors)
        assert any("depends_on" in e for e in res.errors)

        cal_workdays_null = """
calendar:
  workdays: null
"""
        assert validate_calendar(cal_workdays_null).valid is False

        cal_holidays_null = """
calendar:
  holidays: null
"""
        assert validate_calendar(cal_holidays_null).valid is False


class TestLogicalIntegrity:
    """Scenario 5: 論理整合性検証."""

    @pytest.fixture
    def valid_members(self):
        return [
            {"id": "alice", "name": "Alice", "max_capacity": 1.0, "skills": ["frontend", "backend"]},
            {"id": "bob", "name": "Bob", "max_capacity": 0.8, "skills": ["backend", "devops"]},
        ]

    def test_cycle_detection_2_tasks(self, valid_members):
        tasks = [
            {"id": "task-a", "title": "A", "estimate_hours": 8, "depends_on": ["task-b"]},
            {"id": "task-b", "title": "B", "estimate_hours": 8, "depends_on": ["task-a"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any(
            ("task-a -> task-b -> task-a" in e or "task-b -> task-a -> task-b" in e)
            and "循環" in e
            for e in result.errors
        )

    def test_cycle_detection_3_tasks(self, valid_members):
        tasks = [
            {"id": "task-a", "title": "A", "estimate_hours": 8, "depends_on": ["task-b"]},
            {"id": "task-b", "title": "B", "estimate_hours": 8, "depends_on": ["task-c"]},
            {"id": "task-c", "title": "C", "estimate_hours": 8, "depends_on": ["task-a"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any("循環" in e for e in result.errors)

    def test_self_reference(self, valid_members):
        tasks = [
            {"id": "task-self", "title": "Self", "estimate_hours": 8, "depends_on": ["task-self"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any("循環" in e for e in result.errors)

    def test_undefined_task_reference(self, valid_members):
        tasks = [
            {"id": "task-a", "title": "A", "estimate_hours": 8, "depends_on": ["task-nonexistent"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any("未定義のタスク" in e and "task-nonexistent" in e for e in result.errors)

    def test_unmet_skill_requirements(self, valid_members):
        tasks = [
            {"id": "task-special", "title": "Special", "estimate_hours": 8, "required_skills": ["quantum-computing"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any("必須スキル" in e and "quantum-computing" in e for e in result.errors)

    def test_split_skills_across_members_unmet(self, valid_members):
        """Alice has [frontend, backend], Bob has [backend, devops].

        [frontend, devops] cannot be met by any single member.
        """
        tasks = [
            {"id": "task-fullstack", "title": "Fullstack", "estimate_hours": 8, "required_skills": ["frontend", "devops"]},
        ]
        result = validate_logical_integrity(valid_members, tasks)
        assert result.valid is False
        assert any("必須スキル" in e and "frontend, devops" in e for e in result.errors)


class TestActualsSchemaValidation:
    """Milestone 3 Issue #25: actuals.yaml スキーマ・型検証."""

    def test_actuals_yaml_valid_full(self):
        yaml_content = """
work_logs:
  - date: "2026-09-10"
    member_id: "alice"
    task_id: "task-api"
    hours: 6.0
  - date: "2026-09-11"
    member_id: "alice"
    task_id: "task-api"
    hours: 4.5
task_progress:
  - task_id: "task-api"
    remaining_hours: 5.5
    status: "in_progress"
  - task_id: "task-setup"
    remaining_hours: 0.0
    status: "completed"
"""
        result = validate_actuals(yaml_content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.data["work_logs"]) == 2
        assert len(result.data["task_progress"]) == 2
        assert result.data["work_logs"][0]["hours"] == 6.0
        assert result.data["task_progress"][0]["status"] == "in_progress"

    def test_actuals_yaml_only_work_logs(self):
        yaml_content = """
work_logs:
  - date: "2026-09-10"
    member_id: "alice"
    task_id: "task-api"
    hours: 8.0
"""
        result = validate_actuals(yaml_content)
        assert result.valid is True
        assert len(result.data["work_logs"]) == 1
        assert result.data["task_progress"] == []

    def test_actuals_yaml_only_task_progress(self):
        yaml_content = """
task_progress:
  - task_id: "task-api"
    remaining_hours: 4.0
    status: "in_progress"
"""
        result = validate_actuals(yaml_content)
        assert result.valid is True
        assert result.data["work_logs"] == []
        assert len(result.data["task_progress"]) == 1

    def test_actuals_yaml_empty_dict(self):
        result = validate_actuals("{}")
        assert result.valid is True
        assert result.data["work_logs"] == []
        assert result.data["task_progress"] == []

    def test_actuals_yaml_with_root_key(self):
        """actuals: ルートキーでラップされた形式も透過的に許容すること."""
        yaml_content = """
actuals:
  work_logs:
    - date: "2026-09-10"
      member_id: "alice"
      task_id: "task-api"
      hours: 6.0
  task_progress:
    - task_id: "task-api"
      remaining_hours: 5.5
      status: "in_progress"
"""
        result = validate_actuals(yaml_content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.data["work_logs"]) == 1
        assert len(result.data["task_progress"]) == 1
        assert result.data["work_logs"][0]["hours"] == 6.0
        assert result.data["task_progress"][0]["remaining_hours"] == 5.5

    def test_actuals_yaml_with_invalid_root_key(self):
        """actuals: ルートキーの値がオブジェクトでない場合はエラーになること."""
        yaml_content = """
actuals: "invalid"
"""
        result = validate_actuals(yaml_content)
        assert result.valid is False
        assert any("actuals: オブジェクトが必須です" in err for err in result.errors)

    def test_actuals_work_logs_missing_fields(self):
        yaml_missing = """
work_logs:
  - member_id: "alice"
    task_id: "task-api"
  - date: "2026-09-10"
    hours: 4.0
"""
        result = validate_actuals(yaml_missing)
        assert result.valid is False
        assert any("work_logs[0].date" in e for e in result.errors)
        assert any("work_logs[0].hours" in e for e in result.errors)
        assert any("work_logs[1].member_id" in e for e in result.errors)
        assert any("work_logs[1].task_id" in e for e in result.errors)

    def test_actuals_work_logs_invalid_hours(self):
        # 0, negative, string, bool, non-0.1-step
        yaml_zero = "work_logs:\n  - date: '2026-09-10'\n    member_id: alice\n    task_id: t1\n    hours: 0\n"
        assert validate_actuals(yaml_zero).valid is False

        yaml_neg = "work_logs:\n  - date: '2026-09-10'\n    member_id: alice\n    task_id: t1\n    hours: -1.0\n"
        assert validate_actuals(yaml_neg).valid is False

        yaml_str = "work_logs:\n  - date: '2026-09-10'\n    member_id: alice\n    task_id: t1\n    hours: 'four'\n"
        assert validate_actuals(yaml_str).valid is False

        yaml_bool = "work_logs:\n  - date: '2026-09-10'\n    member_id: alice\n    task_id: t1\n    hours: true\n"
        assert validate_actuals(yaml_bool).valid is False

        yaml_step = "work_logs:\n  - date: '2026-09-10'\n    member_id: alice\n    task_id: t1\n    hours: 1.25\n"
        res_step = validate_actuals(yaml_step)
        assert res_step.valid is False
        assert any("0.1 時間刻み" in e for e in res_step.errors)

    def test_actuals_work_logs_invalid_date(self):
        yaml_date = "work_logs:\n  - date: '2026-02-30'\n    member_id: alice\n    task_id: t1\n    hours: 2.0\n"
        res = validate_actuals(yaml_date)
        assert res.valid is False
        assert any("date" in e for e in res.errors)

    def test_actuals_task_progress_missing_fields(self):
        yaml_missing = """
task_progress:
  - task_id: "t1"
"""
        result = validate_actuals(yaml_missing)
        assert result.valid is False
        assert any("remaining_hours" in e for e in result.errors)
        assert any("status" in e for e in result.errors)

    def test_actuals_task_progress_invalid_remaining_hours(self):
        yaml_neg = "task_progress:\n  - task_id: t1\n    remaining_hours: -0.5\n    status: in_progress\n"
        assert validate_actuals(yaml_neg).valid is False

        yaml_step = "task_progress:\n  - task_id: t1\n    remaining_hours: 1.25\n    status: in_progress\n"
        assert validate_actuals(yaml_step).valid is False

    def test_actuals_task_progress_invalid_status(self):
        yaml_status = "task_progress:\n  - task_id: t1\n    remaining_hours: 1.0\n    status: invalid_status\n"
        res = validate_actuals(yaml_status)
        assert res.valid is False
        assert any("status" in e for e in res.errors)

    def test_actuals_task_progress_completed_with_remaining_hours(self):
        yaml_completed = "task_progress:\n  - task_id: t1\n    remaining_hours: 2.0\n    status: completed\n"
        res = validate_actuals(yaml_completed)
        assert res.valid is False
        assert any("0.0" in e and "completed" in e for e in res.errors)

    def test_actuals_task_progress_duplicate_task_id(self):
        yaml_dup = """
task_progress:
  - task_id: t1
    remaining_hours: 2.0
    status: in_progress
  - task_id: t1
    remaining_hours: 0.0
    status: completed
"""
        res = validate_actuals(yaml_dup)
        assert res.valid is False
        assert any("重複" in e for e in res.errors)

    def test_actuals_non_dict_rejected(self):
        assert validate_actuals("[]").valid is False
        assert validate_actuals("work_logs: 'invalid'").valid is False
        assert validate_actuals("task_progress: 'invalid'").valid is False


class TestCalendarAbsencesValidation:
    """Milestone 3 Issue #25: calendar.yaml absences スキーマ・型検証."""

    def test_calendar_with_valid_absences(self):
        yaml_content = """
calendar:
  workdays: [mon, tue, wed, thu, fri]
  absences:
    - member_id: "bob"
      date: "2026-09-16"
      name: "私用休暇"
    - member_id: "alice"
      date: "2026-09-18"
"""
        result = validate_calendar(yaml_content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.data["absences"]) == 2
        assert result.data["absences"][0]["member_id"] == "bob"
        assert result.data["absences"][0]["name"] == "私用休暇"
        assert result.data["absences"][1]["name"] == ""

    def test_calendar_absences_missing_fields(self):
        yaml_missing = """
calendar:
  absences:
    - member_id: "bob"
    - date: "2026-09-16"
"""
        result = validate_calendar(yaml_missing)
        assert result.valid is False
        assert any("absences[0].date" in e for e in result.errors)
        assert any("absences[1].member_id" in e for e in result.errors)

    def test_calendar_absences_invalid_date(self):
        yaml_invalid = """
calendar:
  absences:
    - member_id: "bob"
      date: "2026-02-30"
"""
        result = validate_calendar(yaml_invalid)
        assert result.valid is False
        assert any("date" in e for e in result.errors)

    def test_calendar_absences_invalid_name(self):
        yaml_num_name = """
calendar:
  absences:
    - member_id: "bob"
      date: "2026-09-16"
      name: 123
"""
        assert validate_calendar(yaml_num_name).valid is False

        yaml_null_name = """
calendar:
  absences:
    - member_id: "bob"
      date: "2026-09-16"
      name: null
"""
        assert validate_calendar(yaml_null_name).valid is False

    def test_calendar_absences_duplicate(self):
        yaml_dup = """
calendar:
  absences:
    - member_id: "bob"
      date: "2026-09-16"
      name: "休暇1"
    - member_id: "bob"
      date: "2026-09-16"
      name: "休暇2"
"""
        result = validate_calendar(yaml_dup)
        assert result.valid is False
        assert any("重複" in e for e in result.errors)

    def test_calendar_absences_not_list(self):
        yaml_not_list = "calendar:\n  absences: 'none'\n"
        assert validate_calendar(yaml_not_list).valid is False


class TestActualsLogicalIntegrity:
    """Milestone 3 Issue #25: 実績工数・個別不在の論理整合性検証."""

    @pytest.fixture
    def valid_env(self):
        members = [
            {"id": "alice", "name": "Alice", "max_capacity": 1.0, "skills": ["frontend", "backend"]},
            {"id": "bob", "name": "Bob", "max_capacity": 0.8, "skills": ["backend"]},
        ]
        tasks = [
            {"id": "task-api", "title": "API", "estimate_hours": 16.0, "required_skills": ["backend"], "depends_on": []},
            {"id": "task-ui", "title": "UI", "estimate_hours": 24.0, "required_skills": ["frontend"], "depends_on": ["task-api"]},
        ]
        calendar = {
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "holidays": [],
            "absences": [
                {"member_id": "bob", "date": "2026-09-16", "name": "休暇"},
            ],
        }
        return members, tasks, calendar

    def test_valid_actuals_logical_integrity(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 6.0},
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-ui", "hours": 2.0},
            ],
            "task_progress": [
                {"task_id": "task-api", "remaining_hours": 10.0, "status": "in_progress"},
            ],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is True
        assert len(res.errors) == 0

    def test_undefined_member_in_work_logs(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "charlie", "task_id": "task-api", "hours": 4.0},
            ],
            "task_progress": [],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("未定義のメンバ" in e and "charlie" in e for e in res.errors)

    def test_undefined_member_in_absences(self, valid_env):
        members, tasks, calendar = valid_env
        calendar["absences"] = [
            {"member_id": "charlie", "date": "2026-09-16", "name": "休暇"},
        ]
        res = validate_logical_integrity(members, tasks, calendar)
        assert res.valid is False
        assert any("未定義のメンバ" in e and "charlie" in e for e in res.errors)

    def test_undefined_task_in_work_logs(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-nonexistent", "hours": 4.0},
            ],
            "task_progress": [],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("未定義のタスク" in e and "task-nonexistent" in e for e in res.errors)

    def test_undefined_task_in_task_progress(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [],
            "task_progress": [
                {"task_id": "task-nonexistent", "remaining_hours": 0.0, "status": "completed"},
            ],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("未定義のタスク" in e and "task-nonexistent" in e for e in res.errors)

    def test_daily_work_logs_exceed_24h(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 16.0},
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-ui", "hours": 9.0},
            ],
            "task_progress": [],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("actuals.work_logs[1]:" in e and "24" in e for e in res.errors)

    def test_absence_conflict_with_work_logs(self, valid_env):
        members, tasks, calendar = valid_env
        # Bob is absent on 2026-09-16
        actuals = {
            "work_logs": [
                {"date": "2026-09-16", "member_id": "bob", "task_id": "task-api", "hours": 4.0},
            ],
            "task_progress": [],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("不在" in e and "2026-09-16" in e and "bob" in e for e in res.errors)

    def test_one_task_one_member_violation(self, valid_env):
        members, tasks, calendar = valid_env
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 4.0},
                {"date": "2026-09-11", "member_id": "bob", "task_id": "task-api", "hours": 4.0},
            ],
            "task_progress": [],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("actuals.work_logs[1]:" in e and ("1タスク1担当者" in e or "複数の担当メンバ" in e) for e in res.errors)


class TestProjectDataWithActuals:
    """Milestone 3 Issue #25: validate_project_data の actuals.yaml 統合."""

    def test_project_data_with_valid_actuals(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: "2026-09-10"
    member_id: "alice"
    task_id: "task-api"
    hours: 4.0
task_progress:
  - task_id: "task-api"
    remaining_hours: 12.0
    status: "in_progress"
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert res.actuals is not None
        assert len(res.actuals["work_logs"]) == 1

    def test_project_data_with_actuals_root_key(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """actuals:
  work_logs:
    - date: "2026-09-10"
      member_id: "alice"
      task_id: "task-api"
      hours: 4.0
  task_progress:
    - task_id: "task-api"
      remaining_hours: 12.0
      status: "in_progress"
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert res.actuals is not None
        assert len(res.actuals["work_logs"]) == 1

    def test_project_data_without_actuals_is_valid(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert res.actuals is None

    def test_project_data_with_invalid_actuals_fails(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text("work_logs: 'invalid'\n", encoding="utf-8")
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert len(res.errors) > 0


class TestResolveTaskProgress:
    """Milestone 3 Issue #25 [R4]: FR-8 残工数デフォルト解決ロジックのテスト."""

    def test_resolve_all_omitted(self):
        tasks = [
            {"id": "task-api", "title": "API", "estimate_hours": 16.0},
            {"id": "task-ui", "title": "UI", "estimate_hours": 24.0},
        ]
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 4.0},
                {"date": "2026-09-11", "member_id": "alice", "task_id": "task-api", "hours": 2.0},
            ],
            "task_progress": [],
        }
        resolved = resolve_task_progress(tasks, actuals)
        assert len(resolved) == 2
        api = next(r for r in resolved if r["task_id"] == "task-api")
        assert api["remaining_hours"] == 10.0
        assert api["status"] == "in_progress"
        assert api["total_logged_hours"] == 6.0

        ui = next(r for r in resolved if r["task_id"] == "task-ui")
        assert ui["remaining_hours"] == 24.0
        assert ui["status"] == "not_started"
        assert ui["total_logged_hours"] == 0.0

    def test_resolve_partially_specified(self):
        tasks = [
            {"id": "task-api", "title": "API", "estimate_hours": 16.0},
            {"id": "task-ui", "title": "UI", "estimate_hours": 24.0},
        ]
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 4.0},
            ],
            "task_progress": [
                {"task_id": "task-api", "remaining_hours": 8.0, "status": "in_progress"},
            ],
        }
        resolved = resolve_task_progress(tasks, actuals)
        api = next(r for r in resolved if r["task_id"] == "task-api")
        assert api["remaining_hours"] == 8.0  # 明示的残工数が優先
        assert api["status"] == "in_progress"

        ui = next(r for r in resolved if r["task_id"] == "task-ui")
        assert ui["remaining_hours"] == 24.0  # 未指定タスクは初期見積
        assert ui["status"] == "not_started"

    def test_resolve_logged_exceeds_estimate(self):
        tasks = [
            {"id": "task-api", "title": "API", "estimate_hours": 10.0},
        ]
        actuals = {
            "work_logs": [
                {"date": "2026-09-10", "member_id": "alice", "task_id": "task-api", "hours": 12.0},
            ],
            "task_progress": [],
        }
        resolved = resolve_task_progress(tasks, actuals)
        api = resolved[0]
        assert api["remaining_hours"] == 0.0
        assert api["status"] == "completed"
        assert api["total_logged_hours"] == 12.0

    def test_resolve_no_actuals(self):
        tasks = [
            {"id": "task-api", "title": "API", "estimate_hours": 16.0},
        ]
        resolved = resolve_task_progress(tasks, None)
        api = resolved[0]
        assert api["remaining_hours"] == 16.0
        assert api["status"] == "not_started"
        assert api["total_logged_hours"] == 0.0

    def test_project_data_includes_resolved_progress(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: "2026-09-10"
    member_id: "alice"
    task_id: "task-api"
    hours: 6.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert res.resolved_progress is not None
        api = next(r for r in res.resolved_progress if r["task_id"] == "task-api")
        assert api["remaining_hours"] == 10.0  # 16.0 - 6.0
        assert api["status"] == "in_progress"


class TestValidateProjectDataFormattedErrors:
    """Issue #45: validate_project_data によるエラー整形と formatted_errors の検証."""

    def test_formatted_errors_empty_on_success(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert hasattr(res, "formatted_errors")
        assert res.formatted_errors == []

    def test_formatted_errors_on_schema_error(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            "tasks:\n  - id: task-missing-estimate\n    title: 'Missing estimate'\n",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        assert any(e.startswith("tasks.yaml:") and "estimate_hours" in e for e in res.formatted_errors)

    def test_formatted_errors_on_syntax_error(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            "tasks:\n  - id: task-invalid-yaml\n    title: 'Unclosed\n",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        assert any(e.startswith("tasks.yaml:") and "構文エラー" in e for e in res.formatted_errors)

    def test_formatted_errors_on_logical_error(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            """tasks:
  - id: task-a
    title: Task A
    estimate_hours: 8.0
    depends_on: [task-b]
  - id: task-b
    title: Task B
    estimate_hours: 8.0
    depends_on: [task-a]
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        assert any(e.startswith("tasks.yaml:") and "循環" in e for e in res.formatted_errors)

    def test_formatted_errors_actuals_with_root_key(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """actuals:
  work_logs:
    - date: "2026-09-08"
      member_id: alice
      task_id: task-api
      hours: -5.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        matching = [e for e in res.formatted_errors if e.startswith("actuals.yaml:") and "hours" in e]
        assert len(matching) > 0
        # 1行目ではなく 6 行目付近の該当行が特定されていること
        assert not matching[0].startswith("actuals.yaml:1:")

    def test_formatted_errors_actuals_without_root_key(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: "2026-09-08"
    member_id: alice
    task_id: task-api
    hours: -5.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        matching = [e for e in res.formatted_errors if e.startswith("actuals.yaml:") and "hours" in e]
        assert len(matching) > 0
        assert not matching[0].startswith("actuals.yaml:1:")

    def test_formatted_errors_actuals_logical_error(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: "2026-09-08"
    member_id: alice
    task_id: nonexistent-task
    hours: 4.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert hasattr(res, "formatted_errors")
        assert any(e.startswith("actuals.yaml:") and "未定義" in e for e in res.formatted_errors)


class TestSchemaSymmetryAndDeprecationWarning:
    """Milestone 5 Issue #50: 原本 YAML スキーマのルートキー対称性統一と非推奨警告のテスト (AC-1, AC-2, AC-3)."""

    def test_validation_result_has_warnings_field(self):
        """AC-1: ValidationResult および ProjectValidationResult に warnings フィールドが存在すること."""
        from taskweave.validator import ValidationResult, ProjectValidationResult

        vr = ValidationResult(valid=True)
        assert hasattr(vr, "warnings")
        assert vr.warnings == []

        pvr = ProjectValidationResult(valid=True)
        assert hasattr(pvr, "warnings")
        assert pvr.warnings == []

    def test_validate_actuals_with_root_key_has_no_warnings(self):
        """AC-3: actuals: ルートキー形式の actuals.yaml は warnings なしで正常検証されること."""
        yaml_content = """
actuals:
  work_logs:
    - date: "2026-09-08"
      member_id: "alice"
      task_id: "task-api"
      hours: 4.0
  task_progress:
    - task_id: "task-api"
      remaining_hours: 12.0
      status: "in_progress"
"""
        res = validate_actuals(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        assert res.warnings == []
        assert len(res.data["work_logs"]) == 1
        assert len(res.data["task_progress"]) == 1

    def test_validate_actuals_top_level_has_deprecation_warning(self):
        """AC-2: トップレベル形式の actuals.yaml は非推奨警告が warnings に格納され、透過的に正規化されること."""
        yaml_content = """
work_logs:
  - date: "2026-09-08"
    member_id: "alice"
    task_id: "task-api"
    hours: 4.0
task_progress:
  - task_id: "task-api"
    remaining_hours: 12.0
    status: "in_progress"
"""
        res = validate_actuals(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        assert len(res.warnings) == 1
        assert "非推奨" in res.warnings[0]
        assert "actuals:" in res.warnings[0]
        assert len(res.data["work_logs"]) == 1
        assert len(res.data["task_progress"]) == 1

    def test_validate_actuals_empty_dict_has_no_deprecation_warning(self):
        """[R4]: 空の辞書や無関係キーのみの場合は非推奨警告を発行しないこと."""
        res = validate_actuals("{}")
        assert res.valid is True
        assert res.warnings == []

    def test_validate_actuals_mixed_root_key_and_top_level_rejected(self):
        """[R1]: actuals: ルートキーとトップレベル直下のキーが混在する場合はエラーとなること."""
        yaml_content = """
actuals:
  work_logs:
    - date: "2026-09-08"
      member_id: "alice"
      task_id: "task-api"
      hours: 4.0
work_logs:
  - date: "2026-09-09"
    member_id: "alice"
    task_id: "task-api"
    hours: 2.0
"""
        res = validate_actuals(yaml_content)
        assert res.valid is False
        assert any("同時に存在します" in e for e in res.errors)

    def test_validate_project_data_with_root_key_has_no_warnings(self, tmp_path):
        """AC-3: プロジェクト検証で actuals: ルートキー付き actuals.yaml を読み込んだ場合は warnings なしであること."""
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """actuals:
  work_logs:
    - date: "2026-09-08"
      member_id: alice
      task_id: task-api
      hours: 4.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert len(res.errors) == 0
        assert res.warnings == []
        assert res.actuals is not None
        assert len(res.actuals["work_logs"]) == 1

    def test_validate_project_data_top_level_has_deprecation_warning(self, tmp_path):
        """AC-2: プロジェクト検証でトップレベル形式の actuals.yaml を読み込んだ際、warnings に非推奨警告が格納され透過的に正規化されること."""
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "actuals.yaml").write_text(
            """work_logs:
  - date: "2026-09-08"
    member_id: alice
    task_id: task-api
    hours: 4.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert len(res.errors) == 0
        assert len(res.warnings) == 1
        assert "非推奨" in res.warnings[0]
        assert res.actuals is not None
        assert len(res.actuals["work_logs"]) == 1

    def test_validate_project_data_without_actuals_has_no_warnings(self, tmp_path):
        """actuals.yaml が存在しない場合は warnings なしであること."""
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        res = validate_project_data(tmp_path)
        assert res.valid is True
        assert len(res.errors) == 0
        assert res.warnings == []


class TestTaskAssignmentValidation:
    """Issue #52: タスクの assigned_to および preferred_member のバリデーションテスト."""

    def test_tasks_yaml_with_assigned_to_success(self):
        """AC-1: assigned_to が正常にパースされること."""
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task 1"
    estimate_hours: 8.0
    assigned_to: "alice"
"""
        res = validate_tasks(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        assert len(res.data) == 1
        assert res.data[0]["assigned_to"] == "alice"
        assert res.data[0]["preferred_member"] is None

    def test_tasks_yaml_with_preferred_member_success(self):
        """AC-1: preferred_member が正常にパースされること."""
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task 1"
    estimate_hours: 8.0
    preferred_member: "bob"
"""
        res = validate_tasks(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        assert len(res.data) == 1
        assert res.data[0]["assigned_to"] is None
        assert res.data[0]["preferred_member"] == "bob"

    def test_tasks_yaml_with_both_assigned_to_and_preferred_member_fails(self):
        """AC-5: assigned_to と preferred_member の双方が同一タスクに指定された場合、バリデーションエラーとなること."""
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task 1"
    estimate_hours: 8.0
    assigned_to: "alice"
    preferred_member: "bob"
"""
        res = validate_tasks(yaml_content)
        assert res.valid is False
        assert any("assigned_to" in e and "preferred_member" in e for e in res.errors)

    def test_tasks_yaml_invalid_assigned_to_type(self):
        """assigned_to が文字列でない場合はエラーとなること."""
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task 1"
    estimate_hours: 8.0
    assigned_to: 123
"""
        res = validate_tasks(yaml_content)
        assert res.valid is False
        assert any("tasks[0].assigned_to" in e for e in res.errors)

    def test_tasks_yaml_invalid_preferred_member_type(self):
        """preferred_member が文字列でない場合はエラーとなること."""
        yaml_content = """
tasks:
  - id: "t1"
    title: "Task 1"
    estimate_hours: 8.0
    preferred_member: 456
"""
        res = validate_tasks(yaml_content)
        assert res.valid is False
        assert any("tasks[0].preferred_member" in e for e in res.errors)

    def test_logical_integrity_undefined_assigned_to_member(self):
        """AC-2: members.yaml に存在しないメンバーIDを assigned_to に指定した場合のエラー検知."""
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "estimate_hours": 8.0,
                "required_skills": ["backend"],
                "assigned_to": "charlie",
            }
        ]
        res = validate_logical_integrity(members, tasks)
        assert res.valid is False
        assert any("tasks[0].assigned_to" in e and "charlie" in e for e in res.errors)

    def test_logical_integrity_undefined_preferred_member(self):
        """AC-2: members.yaml に存在しないメンバーIDを preferred_member に指定した場合のエラー検知."""
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "estimate_hours": 8.0,
                "required_skills": ["backend"],
                "preferred_member": "charlie",
            }
        ]
        res = validate_logical_integrity(members, tasks)
        assert res.valid is False
        assert any("tasks[0].preferred_member" in e and "charlie" in e for e in res.errors)

    def test_logical_integrity_skill_mismatch_assigned_to(self):
        """AC-2: assigned_to に指定されたメンバーがタスクの必須スキルを持たない場合のエラー検知."""
        members = [
            {"id": "alice", "name": "Alice", "skills": ["frontend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "estimate_hours": 8.0,
                "required_skills": ["backend"],
                "assigned_to": "alice",  # alice does not have 'backend'
            }
        ]
        res = validate_logical_integrity(members, tasks)
        assert res.valid is False
        assert any("tasks[0].assigned_to" in e and "alice" in e and "backend" in e for e in res.errors)

    def test_logical_integrity_skill_mismatch_preferred_member(self):
        """AC-2: preferred_member に指定されたメンバーがタスクの必須スキルを持たない場合のエラー検知."""
        members = [
            {"id": "alice", "name": "Alice", "skills": ["frontend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "estimate_hours": 8.0,
                "required_skills": ["backend"],
                "preferred_member": "alice",  # alice does not have 'backend'
            }
        ]
        res = validate_logical_integrity(members, tasks)
        assert res.valid is False
        assert any("tasks[0].preferred_member" in e and "alice" in e and "backend" in e for e in res.errors)


class TestValidateScheduleInputsAssignment:
    """[SHOULD] 4: validate_schedule_inputs での assigned_to / preferred_member 検証テスト."""

    def test_both_assigned_to_and_preferred_member_raises_value_error(self):
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [
            {"id": "t1", "estimate_hours": 8.0, "assigned_to": "alice", "preferred_member": "alice"}
        ]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"], "holidays": []}
        with pytest.raises(ValueError, match="assigned_to と preferred_member の両方が指定されています"):
            validate_schedule_inputs(members, tasks, calendar)

    def test_undefined_assigned_to_raises_value_error(self):
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [
            {"id": "t1", "estimate_hours": 8.0, "assigned_to": "charlie"}
        ]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"], "holidays": []}
        with pytest.raises(ValueError, match="担当者 'charlie' .* が members に定義されていません"):
            validate_schedule_inputs(members, tasks, calendar)

    def test_skill_mismatch_assigned_to_raises_value_error(self):
        members = [
            {"id": "alice", "name": "Alice", "skills": ["frontend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [
            {"id": "t1", "estimate_hours": 8.0, "required_skills": ["backend"], "assigned_to": "alice"}
        ]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"], "holidays": []}
        with pytest.raises(ValueError, match="担当者 'alice' .* は必須スキル .* をすべて保有していません"):
            validate_schedule_inputs(members, tasks, calendar)

    def test_undefined_preferred_member_raises_value_error(self):
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [
            {"id": "t1", "estimate_hours": 8.0, "preferred_member": "charlie"}
        ]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"], "holidays": []}
        with pytest.raises(ValueError, match="推奨担当者 'charlie' .* が members に定義されていません"):
            validate_schedule_inputs(members, tasks, calendar)

    def test_skill_mismatch_preferred_member_raises_value_error(self):
        members = [
            {"id": "alice", "name": "Alice", "skills": ["frontend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [
            {"id": "t1", "estimate_hours": 8.0, "required_skills": ["backend"], "preferred_member": "alice"}
        ]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"], "holidays": []}
        with pytest.raises(ValueError, match="推奨担当者 'alice' .* は必須スキル .* をすべて保有していません"):
            validate_schedule_inputs(members, tasks, calendar)


class TestMemberWorkdaysValidation:
    """Issue #51: members.yaml の workdays フィールド構文・論理整合性検証テスト."""

    def test_members_with_valid_workdays(self):
        """AC-1: 有効な workdays を指定した場合、正常にパースされて data に保持されること."""
        yaml_content = """
members:
  - id: alice
    name: "Alice"
    workdays: ["mon", "wed", "fri"]
  - id: bob
    name: "Bob"
"""
        result = validate_members(yaml_content)
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.data[0]["workdays"] == ["mon", "wed", "fri"]
        assert result.data[1].get("workdays") is None

    def test_members_workdays_invalid_types(self):
        """AC-2: workdays が配列でない場合や null、要素が文字列でない場合はエラー."""
        # 文字列
        res1 = validate_members("members:\n  - id: a\n    name: A\n    workdays: 'mon'")
        assert res1.valid is False
        assert any("workdays" in e and "配列" in e for e in res1.errors)

        # null
        res2 = validate_members("members:\n  - id: a\n    name: A\n    workdays: null")
        assert res2.valid is False
        assert any("workdays" in e and "配列" in e for e in res2.errors)

        # 配列内の要素が数値
        res3 = validate_members("members:\n  - id: a\n    name: A\n    workdays: [123]")
        assert res3.valid is False
        assert any("workdays" in e for e in res3.errors)

    def test_members_workdays_invalid_value(self):
        """AC-2: 不正な曜日名が指定された場合はエラー."""
        res = validate_members("members:\n  - id: a\n    name: A\n    workdays: ['mon', 'funday']")
        assert res.valid is False
        assert any("workdays" in e and "funday" in e for e in res.errors)

    def test_members_workdays_duplicate(self):
        """AC-2: 曜日が重複して指定された場合はエラー."""
        res = validate_members("members:\n  - id: a\n    name: A\n    workdays: ['mon', 'wed', 'mon']")
        assert res.valid is False
        assert any("workdays" in e and "重複" in e for e in res.errors)

    def test_members_workdays_empty_list(self):
        """AC-2: 空リストは禁止（少なくとも1つの稼働曜日が必要）."""
        res = validate_members("members:\n  - id: a\n    name: A\n    workdays: []")
        assert res.valid is False
        assert any("workdays" in e and "少なくとも1つ" in e for e in res.errors)

    def test_logical_integrity_member_workdays_not_subset_of_calendar(self):
        """AC-2: メンバーの workdays が calendar.workdays のサブセットでない場合は論理整合性エラー."""
        members = [
            {"id": "alice", "name": "Alice", "workdays": ["mon", "wed", "sat"], "skills": []},
        ]
        tasks = [{"id": "t1", "title": "Task 1", "estimate_hours": 4.0}]
        calendar = {
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "holidays": [],
            "absences": [],
        }
        res = validate_logical_integrity(members, tasks, calendar)
        assert res.valid is False
        assert any("workdays" in e and "sat" in e for e in res.errors)

    def test_validate_project_data_member_workdays_subset_error(self, tmp_path):
        """AC-2: プロジェクト一括検証で行番号付きエラーが出力されること."""
        (tmp_path / "members.yaml").write_text(
            """members:
  - id: alice
    name: Alice
    workdays:
      - mon
      - sat
""",
            encoding="utf-8",
        )
        (tmp_path / "calendar.yaml").write_text(
            """calendar:
  workdays:
    - mon
    - tue
    - wed
    - thu
    - fri
""",
            encoding="utf-8",
        )
        (tmp_path / "tasks.yaml").write_text(
            """tasks:
  - id: task-1
    title: Task 1
    estimate_hours: 4.0
""",
            encoding="utf-8",
        )
        res = validate_project_data(tmp_path)
        assert res.valid is False
        assert any("members.yaml" in e and "sat" in e for e in res.formatted_errors)

    def test_validate_schedule_inputs_member_workdays_not_subset(self):
        """validate_schedule_inputs でも営業日外の曜日指定で ValueError が送出されること."""
        members = [{"id": "alice", "name": "Alice", "workdays": ["mon", "sun"]}]
        tasks = [{"id": "t1", "title": "Task 1", "estimate_hours": 4.0}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        import pytest

        with pytest.raises(ValueError, match="sun"):
            validate_schedule_inputs(members, tasks, calendar)

    def test_logical_integrity_calendar_workdays_non_list_or_non_str(self):
        """[R1]: calendar.workdays がリストでない場合や非文字列要素が含まれてもクラッシュしないこと."""
        members = [{"id": "alice", "name": "Alice", "workdays": ["mon"], "skills": []}]
        tasks = [{"id": "t1", "title": "Task 1", "estimate_hours": 4.0}]
        # 非リスト
        res1 = validate_logical_integrity(members, tasks, {"workdays": "mon"})
        assert isinstance(res1.valid, bool)
        # 非文字列要素混入
        res2 = validate_logical_integrity(members, tasks, {"workdays": [123, "mon"]})
        assert isinstance(res2.valid, bool)

    def test_logical_integrity_error_message_contains_member_id(self):
        """[R4]: エラーメッセージにメンバ ID が含まれること."""
        members = [{"id": "alice", "name": "Alice", "workdays": ["mon", "sat"], "skills": []}]
        tasks = [{"id": "t1", "title": "Task 1", "estimate_hours": 4.0}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        res = validate_logical_integrity(members, tasks, calendar)
        assert res.valid is False
        assert any('メンバ: "alice"' in e for e in res.errors)

    def test_validate_schedule_inputs_workdays_invalid_type_or_empty(self):
        """[R2]: validate_schedule_inputs で workdays の型不正や空配列に ValueError が送出されること."""
        tasks = [{"id": "t1", "title": "Task 1", "estimate_hours": 4.0}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        import pytest

        # 文字列型
        with pytest.raises(ValueError, match="リストである必要があります"):
            validate_schedule_inputs([{"id": "alice", "workdays": "mon"}], tasks, calendar)

        # 空配列
        with pytest.raises(ValueError, match="リストである必要があります"):
            validate_schedule_inputs([{"id": "alice", "workdays": []}], tasks, calendar)

        # 非文字列要素
        with pytest.raises(ValueError, match="calendar.workdays に含まれていません"):
            validate_schedule_inputs([{"id": "alice", "workdays": [123]}], tasks, calendar)


class TestHandoffValidation:
    """Issue #54: タスク引き継ぎ（handoff_to）のスキーマおよび論理整合性検証テスト."""

    def test_actuals_task_progress_valid_handoff_to(self):
        yaml_content = """
actuals:
  task_progress:
    - task_id: task-api
      remaining_hours: 8.0
      status: in_progress
      handoff_to: bob
"""
        res = validate_actuals(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        tp = res.data["task_progress"][0]
        assert tp["task_id"] == "task-api"
        assert tp["handoff_to"] == "bob"

    def test_actuals_task_progress_invalid_handoff_to_type(self):
        yaml_content = """
actuals:
  task_progress:
    - task_id: task-api
      remaining_hours: 8.0
      status: in_progress
      handoff_to: 123
"""
        res = validate_actuals(yaml_content)
        assert res.valid is False
        assert any("handoff_to" in e for e in res.errors)

    def test_actuals_task_progress_empty_handoff_to(self):
        yaml_content = """
actuals:
  task_progress:
    - task_id: task-api
      remaining_hours: 8.0
      status: in_progress
      handoff_to: ""
"""
        res = validate_actuals(yaml_content)
        assert res.valid is False
        assert any("handoff_to" in e for e in res.errors)

    def test_logical_integrity_handoff_to_undefined_member(self):
        members = [{"id": "alice", "name": "Alice", "skills": ["backend"]}]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [{"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 4.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "eve"}],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("未定義のメンバー" in e and "eve" in e for e in res.errors)

    def test_logical_integrity_handoff_to_missing_required_skills(self):
        members = [
            {"id": "alice", "name": "Alice", "skills": ["backend"]},
            {"id": "bob", "name": "Bob", "skills": ["frontend"]},
        ]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [{"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 4.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "bob"}],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("必須スキル" in e and "保有していません" in e for e in res.errors)

    def test_logical_integrity_handoff_to_valid(self):
        members = [
            {"id": "alice", "name": "Alice", "skills": ["backend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend", "frontend"]},
        ]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [{"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 4.0}],
            "task_progress": [{"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "bob"}],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is True
        assert len(res.errors) == 0

    def test_validate_schedule_inputs_handoff_to_undefined_member(self):
        members = [{"id": "alice", "skills": ["backend"]}]
        tasks = [{"id": "t1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "task_progress": [{"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "eve"}],
        }
        with pytest.raises(ValueError, match="未定義"):
            validate_schedule_inputs(members, tasks, calendar, actuals_data=actuals)

    def test_validate_schedule_inputs_handoff_to_missing_skills(self):
        members = [
            {"id": "alice", "skills": ["backend"]},
            {"id": "bob", "skills": ["frontend"]},
        ]
        tasks = [{"id": "t1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "task_progress": [{"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "bob"}],
        }
        with pytest.raises(ValueError, match="必須スキル"):
            validate_schedule_inputs(members, tasks, calendar, actuals_data=actuals)

    def test_actuals_task_progress_explicit_null_handoff_to(self):
        """Issue #54 [MUST] 2:
        actuals.task_progress[].handoff_to に null (または ~) が明示指定された場合、エラーにならず許容されること.
        """
        yaml_content = """
actuals:
  task_progress:
    - task_id: task-api
      remaining_hours: 8.0
      status: in_progress
      handoff_to: null
    - task_id: task-db
      remaining_hours: 4.0
      status: in_progress
      handoff_to: ~
"""
        res = validate_actuals(yaml_content)
        assert res.valid is True
        assert len(res.errors) == 0
        tp0 = res.data["task_progress"][0]
        assert "handoff_to" not in tp0
        tp1 = res.data["task_progress"][1]
        assert "handoff_to" not in tp1

    def test_actuals_task_progress_completed_task_with_handoff_to_fails(self):
        """Issue #54 [IMO] 6:
        完了済みタスク（status: completed または remaining_hours: 0.0）に対して handoff_to が指定された場合エラーになること.
        """
        yaml_content = """
actuals:
  task_progress:
    - task_id: task-api
      remaining_hours: 0.0
      status: completed
      handoff_to: bob
"""
        res = validate_actuals(yaml_content)
        assert res.valid is False
        assert any("完了済みタスク" in e and "handoff_to" in e for e in res.errors)

    def test_logical_integrity_handoff_both_predecessor_and_successor_logs_allowed(self):
        """Issue #54 [MUST] 1:
        引き継ぎタスク (handoff_to が指定されたタスク) では、前任者と後任者の作業ログが両方存在することが許容されること.
        """
        members = [
            {"id": "alice", "name": "Alice", "skills": ["backend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 16.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [
                {"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 8.0},
                {"date": "2026-09-09", "member_id": "bob", "task_id": "t1", "hours": 4.0},
            ],
            "task_progress": [
                {"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "bob"}
            ],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is True
        assert len(res.errors) == 0

    def test_logical_integrity_handoff_third_member_logs_fails(self):
        """Issue #54 [MUST] 1:
        引き継ぎタスクであっても、前任者・後任者以外の第3メンバーの実績が記録されている場合はエラーになること.
        """
        members = [
            {"id": "alice", "name": "Alice", "skills": ["backend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
            {"id": "charlie", "name": "Charlie", "skills": ["backend"]},
        ]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 16.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [
                {"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 4.0},
                {"date": "2026-09-09", "member_id": "bob", "task_id": "t1", "hours": 4.0},
                {"date": "2026-09-10", "member_id": "charlie", "task_id": "t1", "hours": 4.0},
            ],
            "task_progress": [
                {"task_id": "t1", "remaining_hours": 4.0, "status": "in_progress", "handoff_to": "bob"}
            ],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("1タスク1担当者原則" in e or "複数の担当メンバ" in e for e in res.errors)

    def test_logical_integrity_handoff_completed_task_fails(self):
        """Issue #54 [IMO] 6:
        論理整合性検証において完了済みタスクに handoff_to が指定された場合エラーになること.
        """
        members = [
            {"id": "alice", "name": "Alice", "skills": ["backend"]},
            {"id": "bob", "name": "Bob", "skills": ["backend"]},
        ]
        tasks = [{"id": "t1", "title": "T1", "estimate_hours": 8.0, "required_skills": ["backend"]}]
        calendar = {"workdays": ["mon", "tue", "wed", "thu", "fri"]}
        actuals = {
            "work_logs": [{"date": "2026-09-08", "member_id": "alice", "task_id": "t1", "hours": 8.0}],
            "task_progress": [
                {"task_id": "t1", "remaining_hours": 0.0, "status": "completed", "handoff_to": "bob"}
            ],
        }
        res = validate_logical_integrity(members, tasks, calendar, actuals=actuals)
        assert res.valid is False
        assert any("完了済みタスク" in e and "handoff_to" in e for e in res.errors)


