"""Taskweave CLI のテスト.

仕様書: specs/001-yaml-schema.md, CLI validate
"""

from pathlib import Path
import subprocess
import sys
import pytest

BASIC_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "basic"


def run_cli(*args, cwd=None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "taskweave.cli", *args]
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def basic_project_files(tmp_path: Path) -> Path:
    (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


class TestValidateCLI:
    def test_no_subcommand_shows_help_and_exits_zero(self):
        result = run_cli()
        assert result.returncode == 0
        assert "usage: taskweave" in result.stdout
        assert "validate" in result.stdout
        assert result.stderr == ""

    def test_basic_dir_success(self):
        result = run_cli("validate", str(BASIC_DIR))
        assert result.returncode == 0
        assert result.stderr == ""
        assert "検証に成功" in result.stdout

    def test_default_directory_data(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        result = run_cli("validate", cwd=str(tmp_path))
        assert result.returncode == 0
        assert result.stderr == ""
        assert "検証に成功" in result.stdout

    def test_missing_estimate_hours_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text(
            "tasks:\n  - id: task-missing-estimate\n    title: 'Missing estimate'\n",
            encoding="utf-8",
        )

        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "estimate_hours" in result.stderr

    def test_syntax_error_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text(
            "tasks:\n  - id: task-invalid-yaml\n    title: 'Unclosed title\n",
            encoding="utf-8",
        )

        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "構文エラー" in result.stderr

    def test_cycle_dependency_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text(
            """tasks:
  - id: task-a
    title: 'Task A'
    estimate_hours: 8
    depends_on:
      - task-b
  - id: task-b
    title: 'Task B'
    estimate_hours: 8
    depends_on:
      - task-a
""",
            encoding="utf-8",
        )

        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "循環" in result.stderr

    def test_undefined_task_dependency_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text(
            """tasks:
  - id: task-a
    title: 'Task A'
    estimate_hours: 8
    depends_on:
      - task-nonexistent
""",
            encoding="utf-8",
        )

        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "未定義" in result.stderr
        assert "task-nonexistent" in result.stderr

    def test_scalar_root_yaml_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text("false\n", encoding="utf-8")
        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:1:" in result.stderr
        assert "配列が必須です" in result.stderr

    def test_valid_actuals_and_absences_cli_success(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "calendar.yaml").write_text(
            """calendar:
  workdays: [mon, tue, wed, thu, fri]
  absences:
    - member_id: bob
      date: '2026-09-16'
      name: '休暇'
""",
            encoding="utf-8",
        )
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-10'
    member_id: alice
    task_id: task-api
    hours: 4.0
task_progress:
  - task_id: task-api
    remaining_hours: 12.0
    status: in_progress
""",
            encoding="utf-8",
        )
        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 0
        assert result.stderr == ""
        assert "検証に成功" in result.stdout

    def test_invalid_actuals_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-10'
    member_id: alice
    task_id: task-api
    hours: 0.15
""",
            encoding="utf-8",
        )
        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "actuals.yaml:" in result.stderr
        assert "0.1 時間刻み" in result.stderr

    def test_absence_conflict_cli_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "calendar.yaml").write_text(
            """calendar:
  workdays: [mon, tue, wed, thu, fri]
  absences:
    - member_id: alice
      date: '2026-09-10'
      name: '休暇'
""",
            encoding="utf-8",
        )
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-10'
    member_id: alice
    task_id: task-api
    hours: 4.0
""",
            encoding="utf-8",
        )
        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "actuals.yaml:" in result.stderr or "calendar.yaml:" in result.stderr
        assert "不在" in result.stderr

    def test_one_task_multiple_members_reports_file_line(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-10'
    member_id: alice
    task_id: task-api
    hours: 4.0
  - date: '2026-09-11'
    member_id: bob
    task_id: task-api
    hours: 4.0
""",
            encoding="utf-8",
        )
        result = run_cli("validate", str(basic_project_files))
        assert result.returncode == 1
        assert "actuals.yaml:" in result.stderr
        assert "1タスク1担当者" in result.stderr or "複数の担当メンバ" in result.stderr


