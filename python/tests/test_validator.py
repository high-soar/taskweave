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




