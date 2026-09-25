"""Taskweave actuals 記録関数の単体テスト."""

from pathlib import Path
import pytest
import yaml

from taskweave.actuals import record_work_log

BASIC_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "basic"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / "members.yaml").write_text((BASIC_DIR / "members.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "calendar.yaml").write_text((BASIC_DIR / "calendar.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "tasks.yaml").write_text((BASIC_DIR / "tasks.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_record_work_log_invalid_date(project_dir: Path):
    success, errors = record_work_log(
        dir_path=project_dir,
        date="invalid-date",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
    )
    assert not success
    assert any("date" in e for e in errors)


def test_record_work_log_invalid_hours(project_dir: Path):
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=0.05,
    )
    assert not success
    assert any("hours" in e for e in errors)


def test_record_work_log_invalid_remaining_hours(project_dir: Path):
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
        remaining_hours=-1.0,
    )
    assert not success
    assert any("remaining_hours" in e for e in errors)


def test_record_work_log_invalid_status(project_dir: Path):
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
        status="invalid_status",
    )
    assert not success
    assert any("status" in e for e in errors)


def test_record_work_log_missing_master_file(tmp_path: Path):
    # members.yaml 等が存在しないディレクトリ
    success, errors = record_work_log(
        dir_path=tmp_path,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
    )
    assert not success
    assert any("読み込み失敗" in e for e in errors)


def test_record_work_log_corrupted_actuals_yaml(project_dir: Path):
    (project_dir / "actuals.yaml").write_text("corrupted: [yaml: {", encoding="utf-8")
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
    )
    assert not success
    assert any("actuals.yaml 読み込み失敗" in e for e in errors)


def test_record_work_log_non_dict_actuals(project_dir: Path):
    (project_dir / "actuals.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
    )
    assert not success
    assert any("オブジェクトが必須です" in e for e in errors)


def test_record_work_log_success_new_file(project_dir: Path):
    actuals_path = project_dir / "actuals.yaml"
    assert not actuals_path.exists()

    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=8.0,
    )
    assert success
    assert not errors
    assert actuals_path.exists()

    content = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
    assert "actuals" in content
    assert len(content["actuals"]["work_logs"]) == 1
    assert content["actuals"]["work_logs"][0] == {
        "date": "2026-09-08",
        "member_id": "alice",
        "task_id": "task-api",
        "hours": 8.0,
    }


def test_record_work_log_success_add_and_progress_auto_complete(project_dir: Path):
    # 初回記録
    record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=4.0,
    )
    # 加算記録 & completed 指定
    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-08",
        member_id="alice",
        task_id="task-api",
        hours=12.0,
        status="completed",
        add=True,
    )
    assert success
    assert not errors

    content = yaml.safe_load((project_dir / "actuals.yaml").read_text(encoding="utf-8"))
    assert content["actuals"]["work_logs"][0]["hours"] == 16.0
    tp = content["actuals"]["task_progress"][0]
    assert tp["task_id"] == "task-api"
    assert tp["remaining_hours"] == 0.0
    assert tp["status"] == "completed"


def test_record_work_log_migrates_top_level_actuals_to_root_key(project_dir: Path):
    """AC-5: 既存のトップレベル形式 actuals.yaml に対しても、更新時に常に actuals: ルートキー付き形式で正規化書き出しされること."""
    actuals_path = project_dir / "actuals.yaml"
    actuals_path.write_text(
        """work_logs:
  - date: "2026-09-08"
    member_id: alice
    task_id: task-api
    hours: 2.0
task_progress:
  - task_id: task-api
    remaining_hours: 14.0
    status: in_progress
""",
        encoding="utf-8",
    )

    success, errors = record_work_log(
        dir_path=project_dir,
        date="2026-09-09",
        member_id="alice",
        task_id="task-api",
        hours=4.0,
    )
    assert success
    assert not errors

    raw = yaml.safe_load(actuals_path.read_text(encoding="utf-8"))
    assert "actuals" in raw
    assert "work_logs" not in raw
    assert len(raw["actuals"]["work_logs"]) == 2
    assert len(raw["actuals"]["task_progress"]) == 1


