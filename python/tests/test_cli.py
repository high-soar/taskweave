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

    def test_valid_actuals_with_root_key_passes(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """actuals:
  work_logs:
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
        assert "actuals.yaml:5:" in result.stderr
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
        assert "actuals.yaml:2:" in result.stderr
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
        assert "actuals.yaml:6:" in result.stderr
        assert "1タスク1担当者" in result.stderr or "複数の担当メンバ" in result.stderr


class TestReplanCLI:
    """taskweave replan サブコマンドのテスト (AC-4)."""

    def test_replan_help(self):
        result = run_cli("replan", "--help")
        assert result.returncode == 0
        assert "--as-of" in result.stdout
        assert "--format" in result.stdout

    def test_replan_missing_as_of_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("replan", str(basic_project_files))
        assert result.returncode == 2
        assert "--as-of" in result.stderr

    def test_replan_text_output_basic(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-08'
    member_id: alice
    task_id: task-api
    hours: 8.0
task_progress:
  - task_id: task-api
    remaining_hours: 8.0
    status: in_progress
""",
            encoding="utf-8",
        )
        result = run_cli("replan", str(basic_project_files), "--as-of", "2026-09-09")
        assert result.returncode == 0
        assert "Taskweave Replanning & Diff Report" in result.stdout
        assert "Makespan:" in result.stdout

    def test_replan_json_output_basic(self, basic_project_files):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-08'
    member_id: alice
    task_id: task-api
    hours: 8.0
task_progress:
  - task_id: task-api
    remaining_hours: 8.0
    status: in_progress
""",
            encoding="utf-8",
        )
        result = run_cli("replan", str(basic_project_files), "--as-of", "2026-09-09", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "baseline" in data
        assert "replanned" in data
        assert "diff" in data
        assert "makespan" in data["diff"]

    def test_replan_with_explicit_baseline(self, basic_project_files, tmp_path):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(
            json.dumps({
                "status": "OPTIMAL",
                "makespan_workdays": 10,
                "tasks": {
                    "task-setup": {
                        "assigned_to": "alice",
                        "start_date": "2026-09-08",
                        "end_date": "2026-09-08",
                        "workdays_count": 1,
                        "estimate_hours": 8.0,
                        "delay_days": 0,
                    }
                },
            }),
            encoding="utf-8",
        )

        result = run_cli(
            "replan",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--baseline",
            str(baseline_file),
            "--format",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["diff"]["makespan"]["baseline_workdays"] == 10

    def test_replan_validation_error_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text("invalid: yaml: content: [", encoding="utf-8")
        result = run_cli("replan", str(basic_project_files), "--as-of", "2026-09-09")
        assert result.returncode == 1


class TestPlanCLI:
    """taskweave plan サブコマンドのテスト (AC-1 ~ AC-6)."""

    def test_plan_help(self):
        result = run_cli("plan", "--help")
        assert result.returncode == 0
        assert "--format" in result.stdout
        assert "--output" in result.stdout

    def test_plan_basic_text_output(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files))
        assert result.returncode == 0
        assert result.stderr == ""
        assert "Taskweave Schedule Plan Report" in result.stdout
        assert "Status: OPTIMAL" in result.stdout
        assert "Makespan:" in result.stdout
        assert "task-api" in result.stdout
        assert "task-ui" in result.stdout

    def test_plan_default_directory_data(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        result = run_cli("plan", cwd=str(tmp_path))
        assert result.returncode == 0
        assert "Taskweave Schedule Plan Report" in result.stdout

    def test_plan_json_output(self, basic_project_files):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files), "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] in ("OPTIMAL", "FEASIBLE")
        assert "makespan_workdays" in data
        assert "tasks" in data
        assert "task-api" in data["tasks"]
        assert "assigned_to" in data["tasks"]["task-api"]
        assert "start_date" in data["tasks"]["task-api"]
        assert "end_date" in data["tasks"]["task-api"]

    def test_plan_output_file_json_and_replan_compatibility(self, basic_project_files, tmp_path):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "actuals.yaml").write_text(
            """work_logs:
  - date: '2026-09-08'
    member_id: alice
    task_id: task-api
    hours: 8.0
task_progress:
  - task_id: task-api
    remaining_hours: 8.0
    status: in_progress
""",
            encoding="utf-8",
        )
        output_file = tmp_path / "baseline_plan.json"
        result = run_cli(
            "plan",
            str(basic_project_files),
            "--format",
            "json",
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()
        saved_data = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved_data["status"] in ("OPTIMAL", "FEASIBLE")

        # 保存した baseline_plan.json がそのまま replan の --baseline で動作すること
        replan_res = run_cli(
            "replan",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--baseline",
            str(output_file),
            "--format",
            "json",
        )
        assert replan_res.returncode == 0
        replan_data = json.loads(replan_res.stdout)
        assert "diff" in replan_data

    def test_plan_output_file_text(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        output_file = tmp_path / "plan.txt"
        result = run_cli(
            "plan",
            str(basic_project_files),
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Taskweave Schedule Plan Report" in content

    def test_plan_validation_error_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text("invalid: yaml: content: [", encoding="utf-8")
        result = run_cli("plan", str(basic_project_files))
        assert result.returncode == 1
        assert "tasks.yaml:1:" in result.stderr

    def test_plan_with_explicit_start_date(self, basic_project_files):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files), "--start-date", "2026-09-01", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tasks"]["task-api"]["start_date"] == "2026-09-01"

    def test_plan_invalid_start_date_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files), "--start-date", "not-a-date")
        assert result.returncode == 1
        assert "--start-date" in result.stderr

    def test_plan_with_delayed_deadline_diagnostics(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text(
            """tasks:
  - id: task-tight
    title: 'Tight deadline'
    estimate_hours: 16.0
    required_skills:
      - backend
    deadline: '2026-09-02'
""",
            encoding="utf-8",
        )
        result = run_cli("plan", str(basic_project_files), "--start-date", "2026-09-03")
        assert result.returncode == 0
        assert "Delayed Tasks & Diagnostics" in result.stdout
        assert "task-tight" in result.stdout
        assert "納期緩和推奨" in result.stdout

    def test_plan_invalid_arguments_exit_code_2(self):
        result = run_cli("plan", "--format", "invalid_format")
        assert result.returncode == 2

    def test_plan_nonexistent_directory_fails(self):
        result = run_cli("plan", "nonexistent_dir_path")
        assert result.returncode == 1
        assert "読み込み失敗" in result.stderr

    def test_plan_output_creates_parent_directories(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        nested_output = tmp_path / "deeply" / "nested" / "dir" / "plan.json"
        result = run_cli("plan", str(basic_project_files), "--format", "json", "--output", str(nested_output))
        assert result.returncode == 0
        assert nested_output.exists()

    def test_plan_solver_infeasible_status_fails(self, basic_project_files, monkeypatch, capsys):
        from taskweave.cli import main
        import taskweave.engine

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(taskweave.engine, "solve_schedule", lambda **kwargs: {"status": "INFEASIBLE"})
        ret = main(["plan", str(basic_project_files)])
        assert ret == 1
        captured = capsys.readouterr()
        assert "計画の計算が完了しませんでした (ステータス: INFEASIBLE)" in captured.err

    def test_format_plan_summary_none_makespan_and_delay_units(self):
        from taskweave.cli import format_plan_summary

        data = {
            "status": "FEASIBLE",
            "makespan_workdays": None,
            "tasks": {
                "t1": {
                    "assigned_to": "alice",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-02",
                    "workdays_count": 2,
                    "estimate_hours": 16.0,
                    "delay_days": 3,
                }
            },
            "diagnostics": {
                "delayed_tasks": [{"task_id": "t1", "deadline": "2026-08-30", "delay_workdays": 3, "reason": "工数不足"}],
                "recommendations": [],
            },
        }
        text = format_plan_summary(data)
        assert "Makespan: 0 workdays" in text
        assert "[遅延: +3稼働日]" in text


class TestLogCLI:
    def test_log_creates_new_actuals_file_with_root_key(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        if actuals_path.exists():
            actuals_path.unlink()

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
        )
        assert result.returncode == 0
        assert actuals_path.exists()

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert "actuals" in content
        logs = content["actuals"].get("work_logs", [])
        assert len(logs) == 1
        assert logs[0] == {
            "date": "2026-09-08",
            "member_id": "alice",
            "task_id": "task-api",
            "hours": 8.0,
        }

    def test_log_default_directory_data(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (data_dir / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        result = run_cli(
            "log",
            "2026-09-08",
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        actuals_path = data_dir / "actuals.yaml"
        assert actuals_path.exists()

    def test_log_overwrites_existing_log_for_same_day_member_task(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 4.0
""",
            encoding="utf-8",
        )

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "6.0",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        logs = content["actuals"]["work_logs"]
        assert len(logs) == 1
        assert logs[0]["hours"] == 6.0

    def test_log_adds_to_existing_log_with_add_flag(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 4.0
""",
            encoding="utf-8",
        )

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "2.0",
            "--add",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        logs = content["actuals"]["work_logs"]
        assert len(logs) == 1
        assert logs[0]["hours"] == 6.0

    def test_log_appends_new_entry_for_different_date_or_task(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 4.0
""",
            encoding="utf-8",
        )

        result = run_cli(
            "log",
            "2026-09-09",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "4.0",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        logs = content["actuals"]["work_logs"]
        assert len(logs) == 2
        assert logs[0]["date"] == "2026-09-08"
        assert logs[1]["date"] == "2026-09-09"

    def test_log_updates_task_progress(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
            "--remaining", "0.0",
            "--status", "completed",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        tp = content["actuals"].get("task_progress", [])
        assert len(tp) == 1
        assert tp[0] == {
            "task_id": "task-api",
            "remaining_hours": 0.0,
            "status": "completed",
        }

    def test_log_preserves_flat_actuals_structure(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """work_logs:
  - date: 2026-09-08
    member_id: alice
    task_id: task-api
    hours: 4.0
""",
            encoding="utf-8",
        )

        result = run_cli(
            "log",
            "2026-09-09",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "4.0",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert "actuals" not in content
        assert "work_logs" in content
        assert len(content["work_logs"]) == 2

    def test_log_rejects_unknown_member(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "nonexistent_member",
            "--task", "task-api",
            "--hours", "8.0",
        )
        assert result.returncode == 1
        assert "未定義のメンバ" in result.stderr
        assert not (basic_project_files / "actuals.yaml").exists()

    def test_log_rejects_unknown_task(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "nonexistent_task",
            "--hours", "8.0",
        )
        assert result.returncode == 1
        assert "未定義のタスク" in result.stderr
        assert not (basic_project_files / "actuals.yaml").exists()

    def test_log_rejects_absent_date(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        (basic_project_files / "calendar.yaml").write_text(
            """calendar:
  workdays: [mon, tue, wed, thu, fri]
  absences:
    - member_id: alice
      date: 2026-09-08
      reason: 有給休暇
""",
            encoding="utf-8",
        )
        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
        )
        assert result.returncode == 1
        assert "不在" in result.stderr
        assert not (basic_project_files / "actuals.yaml").exists()

    def test_log_rejects_total_hours_exceeding_24h(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 20.0
""",
            encoding="utf-8",
        )
        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "10.0",
            "--add",
        )
        assert result.returncode == 1
        assert "24h" in result.stderr

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert content["actuals"]["work_logs"][0]["hours"] == 20.0

    def test_log_rejects_invalid_hours_or_status(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")

        res1 = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "-1.0",
        )
        assert res1.returncode in (1, 2)

        res2 = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
            "--remaining", "2.0",
            "--status", "completed",
        )
        assert res2.returncode == 1
        assert "completed" in res2.stderr

    def test_log_updates_task_progress_status_only_completed_auto_sets_remaining_zero(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "16.0",
            "--status", "completed",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        tp = content["actuals"]["task_progress"]
        assert len(tp) == 1
        assert tp[0] == {
            "task_id": "task-api",
            "remaining_hours": 0.0,
            "status": "completed",
        }

    def test_log_updates_task_progress_remaining_only_auto_determines_status(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"

        # remaining 8.0 -> in_progress
        result1 = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
            "--remaining", "8.0",
        )
        assert result1.returncode == 0

        import yaml
        content1 = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert content1["actuals"]["task_progress"][0]["status"] == "in_progress"

        # remaining 0.0 -> completed
        result2 = run_cli(
            "log",
            "2026-09-09",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
            "--remaining", "0.0",
        )
        assert result2.returncode == 0

        content2 = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert content2["actuals"]["task_progress"][0]["status"] == "completed"
        assert content2["actuals"]["task_progress"][0]["remaining_hours"] == 0.0

    def test_log_rejects_multiple_members_on_same_task(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 4.0
""",
            encoding="utf-8",
        )
        result = run_cli(
            "log",
            "2026-09-09",
            str(basic_project_files),
            "--member", "bob",
            "--task", "task-api",
            "--hours", "4.0",
        )
        assert result.returncode == 1
        assert "1タスク1担当者" in result.stderr or "複数の担当メンバ" in result.stderr

    def test_log_completed_task_reopened_with_remaining_hours_auto_transitions_to_in_progress(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text(
            """actuals:
  work_logs:
    - date: 2026-09-08
      member_id: alice
      task_id: task-api
      hours: 16.0
  task_progress:
    - task_id: task-api
      remaining_hours: 0.0
      status: completed
""",
            encoding="utf-8",
        )
        result = run_cli(
            "log",
            "2026-09-09",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "2.0",
            "--remaining", "2.0",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        tp = content["actuals"]["task_progress"][0]
        assert tp["status"] == "in_progress"
        assert tp["remaining_hours"] == 2.0

    def test_log_empty_actuals_file_preserves_root_key(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        actuals_path = basic_project_files / "actuals.yaml"
        actuals_path.write_text("", encoding="utf-8")

        result = run_cli(
            "log",
            "2026-09-08",
            str(basic_project_files),
            "--member", "alice",
            "--task", "task-api",
            "--hours", "8.0",
        )
        assert result.returncode == 0

        import yaml
        content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
        assert "actuals" in content
        assert "work_logs" in content["actuals"]


class TestVisualReportingCLI:
    def test_plan_format_mermaid(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files), "--format", "mermaid")
        assert result.returncode == 0
        assert "gantt" in result.stdout
        assert "title Taskweave Schedule Plan" in result.stdout
        assert "section alice" in result.stdout
        assert "task-api" in result.stdout
        assert "task-ui" in result.stdout

    def test_plan_format_markdown(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("plan", str(basic_project_files), "--format", "markdown")
        assert result.returncode == 0
        assert "# スケジュール計画レポート" in result.stdout
        assert "## 全体サマリ" in result.stdout
        assert "## タスク一覧" in result.stdout

    def test_plan_format_mermaid_with_output(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_file = tmp_path / "plan.mermaid"
        result = run_cli("plan", str(basic_project_files), "--format", "mermaid", "--output", str(out_file))
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "gantt" in content
        assert content == result.stdout

    def test_replan_format_mermaid(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("replan", str(basic_project_files), "--as-of", "2026-09-09", "--format", "mermaid")
        assert result.returncode == 0
        assert "gantt" in result.stdout
        assert "title Taskweave Replanned Schedule" in result.stdout

    def test_replan_format_markdown(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        result = run_cli("replan", str(basic_project_files), "--as-of", "2026-09-09", "--format", "markdown")
        assert result.returncode == 0
        assert "# スケジュール再計画レポート" in result.stdout
        assert "## ベースライン比較サマリ" in result.stdout
        assert "## 再計画タスク一覧" in result.stdout

    def test_replan_output_option(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_file = tmp_path / "replan.md"
        result = run_cli(
            "replan",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--format",
            "markdown",
            "--output",
            str(out_file),
        )
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "# スケジュール再計画レポート" in content
        assert content == result.stdout

    def test_replan_output_creates_parent_directories(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        nested_out = tmp_path / "deep" / "nested" / "replan.md"
        result = run_cli(
            "replan",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--format",
            "markdown",
            "--output",
            str(nested_out),
        )
        assert result.returncode == 0
        assert nested_out.exists()
        content = nested_out.read_text(encoding="utf-8")
        assert "# スケジュール再計画レポート" in content


class TestApplyCLI:
    """taskweave apply サブコマンドのテスト (AC-1 ~ AC-5)."""

    def test_apply_help(self):
        result = run_cli("apply", "--help")
        assert result.returncode == 0
        assert "--as-of" in result.stdout
        assert "--baseline" in result.stdout
        assert "--output" in result.stdout
        assert "--no-backup" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--update-tasks" in result.stdout

    def test_apply_new_baseline_creation(self, basic_project_files, tmp_path):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_baseline = tmp_path / "baseline.json"

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--output",
            str(out_baseline),
        )
        assert result.returncode == 0
        assert "Makespan:" in result.stdout
        assert "ベースライン計画を更新しました" in result.stdout
        assert out_baseline.exists()

        data = json.loads(out_baseline.read_text(encoding="utf-8"))
        assert data["status"] in ("OPTIMAL", "FEASIBLE")
        assert "makespan_workdays" in data
        assert "tasks" in data

    def test_apply_default_output_path(self, basic_project_files):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        default_baseline = basic_project_files / "baseline.json"
        if default_baseline.exists():
            default_baseline.unlink()

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
        )
        assert result.returncode == 0
        assert default_baseline.exists()
        data = json.loads(default_baseline.read_text(encoding="utf-8"))
        assert data["status"] in ("OPTIMAL", "FEASIBLE")

    def test_apply_backup_existing_baseline(self, basic_project_files, tmp_path):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_baseline = tmp_path / "baseline.json"
        out_baseline.write_text(json.dumps({"status": "ORIGINAL_OLD"}), encoding="utf-8")

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--output",
            str(out_baseline),
        )
        assert result.returncode == 0
        backup_file = tmp_path / "baseline.json.bak"
        assert backup_file.exists()
        bak_data = json.loads(backup_file.read_text(encoding="utf-8"))
        assert bak_data.get("status") == "ORIGINAL_OLD"

        new_data = json.loads(out_baseline.read_text(encoding="utf-8"))
        assert new_data["status"] in ("OPTIMAL", "FEASIBLE")

    def test_apply_no_backup_flag(self, basic_project_files, tmp_path):
        import json

        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_baseline = tmp_path / "baseline.json"
        out_baseline.write_text(json.dumps({"status": "ORIGINAL_OLD"}), encoding="utf-8")

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--output",
            str(out_baseline),
            "--no-backup",
        )
        assert result.returncode == 0
        backup_file = tmp_path / "baseline.json.bak"
        assert not backup_file.exists()

    def test_apply_dry_run(self, basic_project_files, tmp_path):
        (basic_project_files / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        out_baseline = tmp_path / "baseline.json"

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-09",
            "--output",
            str(out_baseline),
            "--dry-run",
        )
        assert result.returncode == 0
        assert "[Dry Run] ベースラインの更新はスキップされました" in result.stdout
        assert not out_baseline.exists()

    def test_apply_update_tasks_recommendations(self, basic_project_files, tmp_path):
        import yaml

        # 納期が厳しく遅延・納期緩和推奨が発生するタスク原本を作成
        tasks_content = """tasks:
  - id: task-api
    title: API開発
    estimate_hours: 16.0
    required_skills: [backend]
    assigned_to: alice
    deadline: '2026-09-08'
"""
        tasks_file = basic_project_files / "tasks.yaml"
        tasks_file.write_text(tasks_content, encoding="utf-8")

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-08",
            "--update-tasks",
        )
        assert result.returncode == 0
        assert "tasks.yaml を更新しました" in result.stdout

        tasks_bak = basic_project_files / "tasks.yaml.bak"
        assert tasks_bak.exists()

        updated_tasks_raw = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
        updated_tasks = updated_tasks_raw.get("tasks", [])
        task_api = next(t for t in updated_tasks if t["id"] == "task-api")
        # 推奨納期に緩和されていること (2026-09-08 より後)
        assert str(task_api.get("deadline")) > "2026-09-08"

    def test_apply_without_update_tasks_keeps_tasks_yaml_untouched(self, basic_project_files):
        import yaml

        tasks_content = """tasks:
  - id: task-api
    title: API開発
    estimate_hours: 16.0
    required_skills: [backend]
    assigned_to: alice
    deadline: '2026-09-08'
"""
        tasks_file = basic_project_files / "tasks.yaml"
        tasks_file.write_text(tasks_content, encoding="utf-8")

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-08",
        )
        assert result.returncode == 0
        assert not (basic_project_files / "tasks.yaml.bak").exists()
        raw = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
        assert raw["tasks"][0]["deadline"] == "2026-09-08"

    def test_apply_update_tasks_reassignment(self, basic_project_files):
        import json
        import yaml

        # devops スキルを持つ bob に割り当てられるタスク
        tasks_content = """tasks:
  - id: task-infra
    title: インフラ構築
    estimate_hours: 8.0
    required_skills: [devops]
    assigned_to: bob
"""
        tasks_file = basic_project_files / "tasks.yaml"
        tasks_file.write_text(tasks_content, encoding="utf-8")

        # 既存 baseline では alice に割り当てられていたとする
        baseline_file = basic_project_files / "baseline.json"
        baseline_file.write_text(
            json.dumps({
                "status": "OPTIMAL",
                "makespan_workdays": 1,
                "tasks": {
                    "task-infra": {
                        "assigned_to": "alice",
                        "start_date": "2026-09-08",
                        "end_date": "2026-09-08",
                        "workdays_count": 1,
                        "estimate_hours": 8.0,
                        "delay_days": 0,
                    }
                },
            }),
            encoding="utf-8",
        )

        result = run_cli(
            "apply",
            str(basic_project_files),
            "--as-of",
            "2026-09-08",
            "--baseline",
            str(baseline_file),
            "--update-tasks",
        )
        assert result.returncode == 0
        assert "tasks.yaml を更新しました" in result.stdout

        raw = yaml.safe_load(tasks_file.read_text(encoding="utf-8"))
        assert raw["tasks"][0]["assigned_to"] == "bob"

    def test_apply_validation_error_fails(self, basic_project_files):
        (basic_project_files / "tasks.yaml").write_text("invalid: yaml: syntax: [", encoding="utf-8")
        result = run_cli("apply", str(basic_project_files), "--as-of", "2026-09-09")
        assert result.returncode == 1
        assert "tasks.yaml" in result.stderr







