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


class TestValidateCLI:
    def test_basic_dir_success(self):
        result = run_cli("validate", str(BASIC_DIR))
        assert result.returncode == 0
        assert result.stderr == ""
        assert "検証に成功" in result.stdout

    def test_missing_estimate_hours_reports_file_line(self, tmp_path):
        # 正常な members, calendar をコピー
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            "tasks:\n  - id: task-missing-estimate\n    title: 'Missing estimate'\n",
            encoding="utf-8",
        )

        result = run_cli("validate", str(tmp_path))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "estimate_hours" in result.stderr

    def test_syntax_error_reports_file_line(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            "tasks:\n  - id: task-invalid-yaml\n    title: 'Unclosed title\n",
            encoding="utf-8",
        )

        result = run_cli("validate", str(tmp_path))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "構文エラー" in result.stderr

    def test_cycle_dependency_reports_file_line(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
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

        result = run_cli("validate", str(tmp_path))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "循環" in result.stderr

    def test_undefined_task_dependency_reports_file_line(self, tmp_path):
        (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(
            """tasks:
  - id: task-a
    title: 'Task A'
    estimate_hours: 8
    depends_on:
      - task-nonexistent
""",
            encoding="utf-8",
        )

        result = run_cli("validate", str(tmp_path))
        assert result.returncode == 1
        assert "tasks.yaml:" in result.stderr
        assert "未定義" in result.stderr
        assert "task-nonexistent" in result.stderr

