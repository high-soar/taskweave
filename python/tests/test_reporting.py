"""レポーティングモジュール (reporting.py) のテスト.

Mermaid ガントチャート出力および Markdown 表形式出力の検証.
仕様書: specs/005-agent-cli-and-reporting.md (Issue #41)
"""

from __future__ import annotations

import pytest

from taskweave.reporting import (
    _split_daily_hours,
    format_plan_markdown,
    format_plan_mermaid,
    format_replan_markdown,
    format_replan_mermaid,
)


@pytest.fixture
def sample_plan_data():
    return {
        "status": "OPTIMAL",
        "project_start_date": "2026-09-08",
        "makespan_workdays": 3,
        "tasks": {
            "task-setup": {
                "assigned_to": "alice",
                "start_date": "2026-09-08",
                "end_date": "2026-09-08",
                "workdays_count": 1,
                "estimate_hours": 8.0,
                "deadline": None,
                "delay_days": 0,
            },
            "task-api": {
                "assigned_to": "alice",
                "start_date": "2026-09-09",
                "end_date": "2026-09-10",
                "workdays_count": 2,
                "estimate_hours": 16.0,
                "deadline": "2026-09-09",
                "delay_days": 1,
            },
            "task-frontend": {
                "assigned_to": "bob",
                "start_date": "2026-09-09",
                "end_date": "2026-09-10",
                "workdays_count": 2,
                "estimate_hours": 16.0,
                "deadline": None,
                "delay_days": 0,
            },
        },
        "diagnostics": {
            "is_deadline_violated": True,
            "delayed_tasks": [
                {
                    "task_id": "task-api",
                    "deadline": "2026-09-09",
                    "projected_end_date": "2026-09-10",
                    "delay_workdays": 1,
                    "reason": "日別稼働上限に対する工数不足により納期を 1 稼働日超過",
                }
            ],
            "recommendations": [
                {
                    "task_id": "task-api",
                    "action": "extend_deadline",
                    "recommended_deadline": "2026-09-10",
                    "additional_workdays_needed": 1,
                }
            ],
        },
    }


@pytest.fixture
def sample_tasks_data():
    return [
        {"id": "task-setup", "title": "Setup", "estimate_hours": 8.0},
        {"id": "task-api", "title": "API", "estimate_hours": 16.0, "depends_on": ["task-setup"]},
        {"id": "task-frontend", "title": "Frontend", "estimate_hours": 16.0, "depends_on": ["task-setup"]},
    ]


@pytest.fixture
def sample_replan_result():
    return {
        "baseline": {
            "status": "OPTIMAL",
            "makespan_workdays": 3,
            "tasks": {
                "task-setup": {
                    "assigned_to": "alice",
                    "start_date": "2026-09-08",
                    "end_date": "2026-09-08",
                    "workdays_count": 1,
                    "estimate_hours": 8.0,
                    "deadline": None,
                    "delay_days": 0,
                },
                "task-api": {
                    "assigned_to": "alice",
                    "start_date": "2026-09-09",
                    "end_date": "2026-09-10",
                    "workdays_count": 2,
                    "estimate_hours": 16.0,
                    "deadline": "2026-09-10",
                    "delay_days": 0,
                },
            },
        },
        "replanned": {
            "status": "OPTIMAL",
            "as_of_date": "2026-09-09",
            "makespan_workdays": 4,
            "tasks": {
                "task-setup": {
                    "assigned_to": "alice",
                    "start_date": "2026-09-08",
                    "end_date": "2026-09-08",
                    "workdays_count": 1,
                    "estimate_hours": 8.0,
                    "total_logged_hours": 8.0,
                    "remaining_hours": 0.0,
                    "status": "completed",
                    "daily_hours": {"2026-09-08": 8.0},
                    "deadline": None,
                    "delay_days": 0,
                },
                "task-api": {
                    "assigned_to": "alice",
                    "start_date": "2026-09-08",
                    "end_date": "2026-09-11",
                    "workdays_count": 4,
                    "estimate_hours": 16.0,
                    "total_logged_hours": 4.0,
                    "remaining_hours": 16.0,
                    "status": "in_progress",
                    "daily_hours": {
                        "2026-09-08": 4.0,
                        "2026-09-09": 8.0,
                        "2026-09-10": 4.0,
                        "2026-09-11": 4.0,
                    },
                    "deadline": "2026-09-10",
                    "delay_days": 1,
                },
            },
        },
        "diff": {
            "makespan": {
                "baseline_workdays": 3,
                "replanned_workdays": 4,
                "slip_workdays": 1,
            },
            "tasks": {
                "task-setup": {
                    "task_id": "task-setup",
                    "baseline": {"start_date": "2026-09-08", "end_date": "2026-09-08"},
                    "replanned": {"start_date": "2026-09-08", "end_date": "2026-09-08", "status": "completed"},
                    "diff": {"start_date_slip_days": 0, "end_date_slip_days": 0},
                    "diagnostics": {"is_delayed": False, "reasons": [], "details": []},
                },
                "task-api": {
                    "task_id": "task-api",
                    "baseline": {"start_date": "2026-09-09", "end_date": "2026-09-10"},
                    "replanned": {"start_date": "2026-09-09", "end_date": "2026-09-11", "status": "in_progress"},
                    "diff": {"start_date_slip_days": 0, "end_date_slip_days": 1},
                    "diagnostics": {
                        "is_delayed": True,
                        "primary_reason": "workload_increase",
                        "reasons": ["workload_increase"],
                        "details": ["見積工数 (16.0h) に対し、実績および残工数合計 (20.0h) が超過 (+4.0h)"],
                    },
                },
            },
            "summary": {
                "total_tasks": 2,
                "delayed_tasks_count": 1,
                "delayed_task_ids": ["task-api"],
            },
            "recommendations": [
                {
                    "task_id": "task-api",
                    "current_deadline": "2026-09-10",
                    "recommended_deadline": "2026-09-11",
                    "delay_days": 1,
                    "message": "タスク 'task-api' の納期を 2026-09-11 以降に緩和することを推奨します",
                }
            ],
        },
    }


class TestReportingPlan:
    def test_format_plan_mermaid_basic(self, sample_plan_data, sample_tasks_data):
        chart = format_plan_mermaid(sample_plan_data, sample_tasks_data)
        assert chart.startswith("```mermaid\ngantt\n")
        assert chart.endswith("```")
        assert "title Taskweave Schedule Plan" in chart
        assert "dateFormat YYYY-MM-DD" in chart
        assert "section alice" in chart
        assert "section bob" in chart
        # task-setup
        assert "task-setup : task-setup, 2026-09-08, 2026-09-08" in chart
        # task-api has dependency on task-setup and delay -> crit
        assert "crit" in chart
        assert "after task-setup" in chart
        assert "task-api" in chart

    def test_format_plan_markdown_basic(self, sample_plan_data):
        doc = format_plan_markdown(sample_plan_data)
        assert "# スケジュール計画レポート" in doc
        assert "## 全体サマリ" in doc
        assert "| ステータス | OPTIMAL |" in doc
        assert "3 稼働日" in doc
        assert "## タスク一覧" in doc
        assert "| task-setup | alice | 2026-09-08 | 2026-09-08 | 1 | 8.0h |" in doc
        assert "| task-api | alice | 2026-09-09 | 2026-09-10 | 2 | 16.0h | 2026-09-09 | +1日 |" in doc
        assert "## 担当者別工数サマリ" in doc
        assert "| alice | 2 | 24.0h |" in doc
        assert "| bob | 1 | 16.0h |" in doc
        assert "## 遅延タスク診断" in doc
        assert "## 納期緩和推奨" in doc

    def test_format_plan_with_none_values(self):
        plan_data = {
            "status": "OPTIMAL",
            "makespan_workdays": 1,
            "tasks": {
                "task-none": {
                    "assigned_to": None,
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-01",
                    "workdays_count": 1,
                    "estimate_hours": None,
                }
            },
        }
        # Markdown テーブルで None が crash せず unassigned / 0.0h になること
        doc = format_plan_markdown(plan_data)
        assert "| task-none | unassigned | 2026-09-01 | 2026-09-01 | 1 | 0.0h |" in doc
        assert "| unassigned | 1 | 0.0h |" in doc

        # Mermaid で section unassigned になること
        chart = format_plan_mermaid(plan_data)
        assert "section unassigned" in chart
        assert "task-none : task-none, 2026-09-01, 2026-09-01" in chart


class TestReportingReplan:
    def test_format_replan_mermaid_with_actuals_and_progress(self, sample_replan_result):
        chart = format_replan_mermaid(sample_replan_result)
        assert chart.startswith("```mermaid\ngantt\n")
        assert "title Taskweave Replanned Schedule" in chart
        assert "section alice" in chart
        # completed task has done tag
        assert "task-setup" in chart
        assert "done" in chart
        # in_progress task has actuals (done) and remaining (active/crit)
        assert "[実績] : done" in chart
        assert "[残工数] : active" in chart or "[残工数] : crit, active" in chart

    def test_format_replan_mermaid_in_progress_edge_cases(self):
        # 1. daily_hours が空の場合 -> 単一バーで active
        data_empty_daily = {
            "replanned": {
                "as_of_date": "2026-09-09",
                "tasks": {
                    "t1": {
                        "assigned_to": "alice",
                        "status": "in_progress",
                        "start_date": "2026-09-09",
                        "end_date": "2026-09-10",
                        "remaining_hours": 8.0,
                        "daily_hours": {},
                    }
                },
            },
            "diff": {"tasks": {}},
        }
        chart1 = format_replan_mermaid(data_empty_daily)
        assert "t1 : active, t1, 2026-09-09, 2026-09-10" in chart1

        # 2. 実績のみ存在する場合 -> [実績] のみ
        data_past_only = {
            "replanned": {
                "as_of_date": "2026-09-09",
                "tasks": {
                    "t2": {
                        "assigned_to": "alice",
                        "status": "in_progress",
                        "start_date": "2026-09-08",
                        "end_date": "2026-09-09",
                        "daily_hours": {"2026-09-08": 8.0},
                    }
                },
            },
            "diff": {"tasks": {}},
        }
        chart2 = format_replan_mermaid(data_past_only)
        assert "t2 [実績] : done, t2-actual, 2026-09-08, 2026-09-08" in chart2
        assert "[残工数]" not in chart2

        # 3. 残工数のみ存在する場合 -> [残工数] のみ
        data_future_only = {
            "replanned": {
                "as_of_date": "2026-09-09",
                "tasks": {
                    "t3": {
                        "assigned_to": "alice",
                        "status": "in_progress",
                        "start_date": "2026-09-10",
                        "end_date": "2026-09-11",
                        "remaining_hours": 16.0,
                        "daily_hours": {"2026-09-10": 8.0, "2026-09-11": 8.0},
                    }
                },
            },
            "diff": {"tasks": {}},
        }
        chart3 = format_replan_mermaid(data_future_only)
        assert "t3 [残工数] : active, t3, 2026-09-10, 2026-09-11" in chart3
        assert "[実績]" not in chart3

    def test_format_replan_markdown_with_diff_and_diagnostics(self, sample_replan_result):
        doc = format_replan_markdown(sample_replan_result)
        assert "# スケジュール再計画レポート" in doc
        assert "## ベースライン比較サマリ" in doc
        assert "3 稼働日" in doc
        assert "4 稼働日" in doc
        assert "+1 稼働日" in doc
        assert "## 遅延タスク診断 (Delayed Tasks & Diagnostics)" in doc
        assert "task-api" in doc
        assert "工数超過 (workload_increase)" in doc
        assert "+1日" in doc
        assert "## 再計画タスク一覧 (Replanned Tasks)" in doc
        assert "task-setup" in doc
        assert "completed" in doc
        assert "## 納期緩和推奨 (Recommendations)" in doc

    def test_format_replan_markdown_no_delays(self):
        replan_no_delays = {
            "baseline": {"makespan_workdays": 3, "tasks": {"t1": {"delay_days": 0}}},
            "replanned": {
                "makespan_workdays": 3,
                "tasks": {
                    "t1": {
                        "assigned_to": None,
                        "status": "not_started",
                        "start_date": "2026-09-01",
                        "end_date": "2026-09-03",
                        "workdays_count": 3,
                        "total_logged_hours": 0.0,
                        "remaining_hours": 24.0,
                        "delay_days": 0,
                    }
                },
            },
            "diff": {
                "makespan": {"baseline_workdays": 3, "replanned_workdays": 3, "slip_workdays": 0},
                "tasks": {},
                "summary": {"delayed_task_ids": []},
                "recommendations": [],
            },
        }
        doc = format_replan_markdown(replan_no_delays)
        assert "遅延タスクはありません。計画通り進行しています。" in doc
        assert "| 遅延タスク数 | 0 | 0 | +0 |" in doc
        assert "| t1 | unassigned | not_started |" in doc

    def test_format_replan_mermaid_handoff_split(self):
        """Issue #54 (AC-5):
        引き継ぎタスク (handoff) において、前任者のセクションに過去実績 [実績]、
        後任者のセクションに未来残工数 [残工数] が分割描画されること.
        """
        replan_result = {
            "replanned": {
                "as_of_date": "2026-09-09",
                "tasks": {
                    "task-api": {
                        "assigned_to": "bob",
                        "status": "in_progress",
                        "start_date": "2026-09-08",
                        "end_date": "2026-09-10",
                        "estimate_hours": 16.0,
                        "total_logged_hours": 8.0,
                        "remaining_hours": 8.0,
                        "daily_hours": {
                            "2026-09-08": 8.0,
                            "2026-09-09": 8.0,
                        },
                        "handoff": {
                            "from": "alice",
                            "as_of": "2026-09-09",
                        },
                    }
                },
            },
            "diff": {"tasks": {}},
        }
        chart = format_replan_mermaid(replan_result)
        assert "section alice" in chart
        assert "section bob" in chart
        alice_section = chart.split("section alice")[1].split("section bob")[0]
        bob_section = chart.split("section bob")[1]

        assert "task-api [実績] : done, task-api-actual, 2026-09-08, 2026-09-08" in alice_section
        assert "[残工数]" not in alice_section

        assert "task-api [残工数] : active, task-api, 2026-09-09, 2026-09-09" in bob_section
        assert "[実績]" not in bob_section

    def test_format_replan_markdown_handoff_split(self):
        """Issue #54 (AC-5):
        Markdown 表出力において、引き継ぎタスクが前任者の過去実績と後任者の未来残工数に矛盾なく分割表示されること.
        """
        replan_result = {
            "baseline": {"makespan_workdays": 2, "tasks": {}},
            "replanned": {
                "as_of_date": "2026-09-09",
                "makespan_workdays": 2,
                "tasks": {
                    "task-api": {
                        "assigned_to": "bob",
                        "status": "in_progress",
                        "start_date": "2026-09-08",
                        "end_date": "2026-09-09",
                        "workdays_count": 2,
                        "estimate_hours": 16.0,
                        "total_logged_hours": 8.0,
                        "remaining_hours": 8.0,
                        "daily_hours": {
                            "2026-09-08": 8.0,
                            "2026-09-09": 8.0,
                        },
                        "handoff": {
                            "from": "alice",
                            "as_of": "2026-09-09",
                        },
                    }
                },
            },
            "diff": {
                "makespan": {"baseline_workdays": 2, "replanned_workdays": 2, "slip_workdays": 0},
                "tasks": {},
                "summary": {"delayed_task_ids": []},
                "recommendations": [],
            },
        }
        doc = format_replan_markdown(replan_result)
        assert "| task-api [実績] | alice |" in doc
        assert "| task-api [残工数] | bob |" in doc

    def test_format_replan_markdown_handoff_unstarted_task_no_actuals_row(self):
        """Issue #54 [SHOULD] 3:
        未着手（実績ゼロ）の引き継ぎタスクで架空の [実績] 行が出力されないこと.
        """
        replan_result = {
            "baseline": {"makespan_workdays": 1, "tasks": {}},
            "replanned": {
                "as_of_date": "2026-09-09",
                "makespan_workdays": 1,
                "tasks": {
                    "task-api": {
                        "assigned_to": "bob",
                        "status": "not_started",
                        "start_date": "2026-09-09",
                        "end_date": "2026-09-09",
                        "workdays_count": 1,
                        "estimate_hours": 8.0,
                        "total_logged_hours": 0.0,
                        "remaining_hours": 8.0,
                        "daily_hours": {
                            "2026-09-09": 8.0,
                        },
                        "handoff": {
                            "from": "alice",
                            "as_of": "2026-09-09",
                        },
                    }
                },
            },
            "diff": {
                "makespan": {"baseline_workdays": 1, "replanned_workdays": 1, "slip_workdays": 0},
                "tasks": {},
                "summary": {"delayed_task_ids": []},
                "recommendations": [],
            },
        }
        doc = format_replan_markdown(replan_result)
        assert "[実績]" not in doc
        assert "| task-api [残工数] | bob |" in doc

    def test_split_daily_hours_boundary(self):
        """Issue #54 [SHOULD] 4:
        _split_daily_hours が specs/004 FR-10 に従い、
        d < cutoff を過去実績、d >= cutoff を未来予定に正確に分割すること.
        """
        daily = {
            "2026-09-08": 8.0,
            "2026-09-09": 4.0,
            "2026-09-10": 8.0,
        }
        past, future = _split_daily_hours(daily, "2026-09-09")
        assert past == ["2026-09-08"]
        assert future == ["2026-09-09", "2026-09-10"]

        # 空データや None のケース
        assert _split_daily_hours({}, "2026-09-09") == ([], [])
        assert _split_daily_hours(daily, None) == ([], [])
        assert _split_daily_hours(None, "2026-09-09") == ([], [])




