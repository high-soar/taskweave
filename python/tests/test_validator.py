"""YAML 原本データおよび論理整合性バリデータのテスト.

仕様書: specs/001-yaml-schema.md
"""

from pathlib import Path
import pytest
from taskweave.validator import (
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

