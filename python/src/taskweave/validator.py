"""Taskweave 原本 YAML スキーマおよび論理整合性バリデータ.

仕様書: specs/001-yaml-schema.md
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any
import yaml

VALID_WORKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_TASK_STATUSES = {"not_started", "in_progress", "completed"}


@dataclass
class ValidationResult:
    """単一ファイルの検証結果."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    data: Any = None


@dataclass
class ProjectValidationResult:
    """プロジェクト全体の検証結果."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    members: list[dict[str, Any]] | None = None
    tasks: list[dict[str, Any]] | None = None
    calendar: dict[str, Any] | None = None
    actuals: dict[str, Any] | None = None
    resolved_progress: list[dict[str, Any]] | None = None


def is_valid_date(val: Any) -> bool:
    """有効な YYYY-MM-DD 形式の日付文字列であるかを検証する."""
    if not isinstance(val, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return False
    try:
        datetime.date.fromisoformat(val)
        return True
    except ValueError:
        return False


def is_valid_estimate_hours(val: Any) -> bool:
    """見積工数が 0.1 以上の 0.1 時間刻み（小数点以下1桁まで）の正の数値であるかを検証する."""
    return (
        val is not None
        and isinstance(val, (int, float))
        and not isinstance(val, bool)
        and math.isfinite(val)
        and val >= 0.1
        and abs(val - round(val * 10) / 10) < 1e-6
    )


def is_valid_remaining_hours(val: Any) -> bool:
    """残工数が 0.0 以上の 0.1 時間刻み（小数点以下1桁まで）の有限な数値であるかを検証する."""
    return (
        val is not None
        and isinstance(val, (int, float))
        and not isinstance(val, bool)
        and math.isfinite(val)
        and val >= 0.0
        and abs(val - round(val * 10) / 10) < 1e-6
    )



def parse_yaml(yaml_string: str, errors: list[str]) -> Any:
    """YAML 文字列をパースし、空や構文エラーを検知する."""
    if not isinstance(yaml_string, str) or yaml_string.strip() == "":
        errors.append("YAML ドキュメントが空です")
        return None
    try:
        parsed = yaml.safe_load(yaml_string)
        if parsed is None:
            errors.append("YAML にデータが含まれていません")
            return None
        return parsed
    except yaml.YAMLError as err:
        errors.append(f"YAML 構文エラー: {err}")
        return None


def validate_members(yaml_string: str) -> ValidationResult:
    """members.yaml のスキーマを検証する."""
    errors: list[str] = []
    parsed = parse_yaml(yaml_string, errors)
    if parsed is None:
        return ValidationResult(valid=False, errors=errors, data=[])

    if not isinstance(parsed, dict) or "members" not in parsed or not isinstance(parsed["members"], list):
        errors.append("members: 配列が必須です")
        return ValidationResult(valid=False, errors=errors, data=[])

    seen_ids: set[str] = set()
    members: list[dict[str, Any]] = []

    for i, m in enumerate(parsed["members"]):
        prefix = f"members[{i}]"
        if not isinstance(m, dict):
            errors.append(f"{prefix}: オブジェクトである必要があります")
            continue

        m_id = m.get("id")
        if not isinstance(m_id, str) or not m_id:
            errors.append(f"{prefix}.id: 必須の文字列です")
        elif m_id in seen_ids:
            errors.append(f'{prefix}.id: "{m_id}" は重複しています')
        else:
            seen_ids.add(m_id)

        m_name = m.get("name")
        if not isinstance(m_name, str) or not m_name:
            errors.append(f"{prefix}.name: 必須の文字列です")

        max_capacity = 1.0
        if "max_capacity" in m:
            val = m["max_capacity"]
            if (
                val is None
                or not isinstance(val, (int, float))
                or isinstance(val, bool)
                or not math.isfinite(val)
                or val <= 0.0
                or val > 1.0
            ):
                errors.append(
                    f"{prefix}.max_capacity: 0.0 超 1.0 以下の有限な数値である必要があります (指定値: {val})"
                )
            else:
                max_capacity = float(val)

        skills: list[str] = []
        if "skills" in m:
            raw_skills = m["skills"]
            if raw_skills is None or not isinstance(raw_skills, list) or any(not isinstance(s, str) for s in raw_skills):
                errors.append(f"{prefix}.skills: 文字列の配列である必要があります")
            else:
                skills = raw_skills

        members.append({
            "id": m_id,
            "name": m_name,
            "max_capacity": max_capacity,
            "skills": skills,
        })

    return ValidationResult(valid=len(errors) == 0, errors=errors, data=members)


def validate_tasks(yaml_string: str) -> ValidationResult:
    """tasks.yaml のスキーマを検証する."""
    errors: list[str] = []
    parsed = parse_yaml(yaml_string, errors)
    if parsed is None:
        return ValidationResult(valid=False, errors=errors, data=[])

    if not isinstance(parsed, dict) or "tasks" not in parsed or not isinstance(parsed["tasks"], list):
        errors.append("tasks: 配列が必須です")
        return ValidationResult(valid=False, errors=errors, data=[])

    seen_ids: set[str] = set()
    tasks: list[dict[str, Any]] = []

    for i, t in enumerate(parsed["tasks"]):
        prefix = f"tasks[{i}]"
        if not isinstance(t, dict):
            errors.append(f"{prefix}: オブジェクトである必要があります")
            continue

        t_id = t.get("id")
        if not isinstance(t_id, str) or not t_id:
            errors.append(f"{prefix}.id: 必須の文字列です")
        elif t_id in seen_ids:
            errors.append(f'{prefix}.id: "{t_id}" は重複しています')
        else:
            seen_ids.add(t_id)

        t_title = t.get("title")
        if not isinstance(t_title, str) or not t_title:
            errors.append(f"{prefix}.title: 必須の文字列です")

        est = t.get("estimate_hours")
        is_step_01 = is_valid_estimate_hours(est)
        if not is_step_01:
            errors.append(
                f"{prefix}.estimate_hours: 0.1 以上の 0.1 時間刻み（小数点以下1桁まで）の正の数値である必要があります"
            )

        required_skills: list[str] = []
        if "required_skills" in t:
            raw_req = t["required_skills"]
            if raw_req is None or not isinstance(raw_req, list) or any(not isinstance(s, str) for s in raw_req):
                errors.append(f"{prefix}.required_skills: 文字列の配列である必要があります")
            else:
                required_skills = raw_req

        depends_on: list[str] = []
        if "depends_on" in t:
            raw_dep = t["depends_on"]
            if raw_dep is None or not isinstance(raw_dep, list) or any(not isinstance(d, str) for d in raw_dep):
                errors.append(f"{prefix}.depends_on: 文字列の配列である必要があります")
            else:
                depends_on = raw_dep

        deadline = None
        if "deadline" in t and t["deadline"] is not None:
            raw_dl = t["deadline"]
            dl_str = raw_dl.isoformat() if isinstance(raw_dl, (datetime.date, datetime.datetime)) else str(raw_dl)
            if not is_valid_date(dl_str):
                errors.append(
                    f"{prefix}.deadline: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: {raw_dl})"
                )
            else:
                deadline = dl_str

        tasks.append({
            "id": t_id,
            "title": t_title,
            "estimate_hours": float(est) if is_step_01 else est,
            "required_skills": required_skills,
            "depends_on": depends_on,
            "deadline": deadline,
        })

    return ValidationResult(valid=len(errors) == 0, errors=errors, data=tasks)


def validate_actuals(yaml_string: str) -> ValidationResult:
    """actuals.yaml のスキーマを検証する."""
    errors: list[str] = []
    parsed = parse_yaml(yaml_string, errors)
    if parsed is None:
        return ValidationResult(valid=False, errors=errors, data={"work_logs": [], "task_progress": []})

    if not isinstance(parsed, dict):
        errors.append("actuals: オブジェクトが必須です")
        return ValidationResult(valid=False, errors=errors, data={"work_logs": [], "task_progress": []})

    work_logs: list[dict[str, Any]] = []
    if "work_logs" in parsed:
        raw_wl = parsed["work_logs"]
        if raw_wl is None or not isinstance(raw_wl, list):
            errors.append("actuals.work_logs: 配列である必要があります")
        else:
            for i, wl in enumerate(raw_wl):
                prefix = f"actuals.work_logs[{i}]"
                if not isinstance(wl, dict):
                    errors.append(f"{prefix}: オブジェクトである必要があります")
                    continue

                d = wl.get("date")
                d_str = (
                    d.isoformat()
                    if isinstance(d, (datetime.date, datetime.datetime))
                    else str(d)
                    if d is not None
                    else None
                )
                if d_str is None or not is_valid_date(d_str):
                    errors.append(
                        f"{prefix}.date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: {d})"
                    )

                m_id = wl.get("member_id")
                if not isinstance(m_id, str) or not m_id:
                    errors.append(f"{prefix}.member_id: 必須の文字列です")

                t_id = wl.get("task_id")
                if not isinstance(t_id, str) or not t_id:
                    errors.append(f"{prefix}.task_id: 必須の文字列です")

                h = wl.get("hours")
                is_step_01 = is_valid_estimate_hours(h)
                if not is_step_01:
                    errors.append(
                        f"{prefix}.hours: 0.1 以上の 0.1 時間刻み（小数点以下1桁まで）の正の数値である必要があります (指定値: {h})"
                    )

                work_logs.append({
                    "date": d_str,
                    "member_id": m_id,
                    "task_id": t_id,
                    "hours": float(h) if is_step_01 else h,
                })

    task_progress: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    if "task_progress" in parsed:
        raw_tp = parsed["task_progress"]
        if raw_tp is None or not isinstance(raw_tp, list):
            errors.append("actuals.task_progress: 配列である必要があります")
        else:
            for i, tp in enumerate(raw_tp):
                prefix = f"actuals.task_progress[{i}]"
                if not isinstance(tp, dict):
                    errors.append(f"{prefix}: オブジェクトである必要があります")
                    continue

                t_id = tp.get("task_id")
                if not isinstance(t_id, str) or not t_id:
                    errors.append(f"{prefix}.task_id: 必須の文字列です")
                elif t_id in seen_tasks:
                    errors.append(f'{prefix}.task_id: "{t_id}" は重複しています')
                else:
                    seen_tasks.add(t_id)

                rem = tp.get("remaining_hours")
                is_valid_rem = is_valid_remaining_hours(rem)
                if not is_valid_rem:
                    errors.append(
                        f"{prefix}.remaining_hours: 0.0 以上の 0.1 時間刻み（小数点以下1桁まで）の数値である必要があります (指定値: {rem})"
                    )

                status = tp.get("status")
                if not isinstance(status, str) or status not in VALID_TASK_STATUSES:
                    errors.append(
                        f"{prefix}.status: 有効なステータス ({', '.join(sorted(VALID_TASK_STATUSES))}) である必要があります (指定値: {status})"
                    )
                elif status == "completed" and is_valid_rem and float(rem) != 0.0:
                    errors.append(
                        f'{prefix}: status が "completed" の場合、remaining_hours は 0.0 である必要があります (指定値: {rem})'
                    )

                task_progress.append({
                    "task_id": t_id,
                    "remaining_hours": float(rem) if is_valid_rem else rem,
                    "status": status,
                })

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        data={"work_logs": work_logs, "task_progress": task_progress},
    )


def validate_calendar(yaml_string: str) -> ValidationResult:
    """calendar.yaml のスキーマを検証する."""
    errors: list[str] = []
    parsed = parse_yaml(yaml_string, errors)
    if parsed is None:
        return ValidationResult(valid=False, errors=errors, data=None)

    if not isinstance(parsed, dict) or "calendar" not in parsed:
        errors.append("calendar: オブジェクトが必須です")
        return ValidationResult(valid=False, errors=errors, data=None)

    cal = parsed["calendar"]
    if not isinstance(cal, dict):
        errors.append("calendar: オブジェクトが必須です")
        return ValidationResult(valid=False, errors=errors, data=None)

    workdays = ["mon", "tue", "wed", "thu", "fri"]
    if "workdays" in cal:
        raw_wd = cal["workdays"]
        if raw_wd is None or not isinstance(raw_wd, list):
            errors.append(
                "calendar.workdays: 有効な曜日 (mon, tue, wed, thu, fri, sat, sun) の配列である必要があります"
            )
        elif any(w not in VALID_WORKDAYS for w in raw_wd):
            invalid_items = [repr(w) for w in raw_wd if w not in VALID_WORKDAYS]
            errors.append(
                f"calendar.workdays: 有効な曜日 (mon, tue, wed, thu, fri, sat, sun) の配列である必要があります (不正な要素: {', '.join(invalid_items)})"
            )
        elif len(raw_wd) == 0:
            errors.append("calendar.workdays: 少なくとも1つの有効な稼働曜日を指定する必要があります")
        else:
            seen_wd: set[str] = set()
            has_dup = False
            for w in raw_wd:
                if w in seen_wd:
                    errors.append(f'calendar.workdays: "{w}" は重複しています')
                    has_dup = True
                seen_wd.add(w)
            if not has_dup:
                workdays = raw_wd

    holidays: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    if "holidays" in cal:
        raw_hd = cal["holidays"]
        if raw_hd is None or not isinstance(raw_hd, list):
            errors.append("calendar.holidays: 配列である必要があります")
        else:
            for i, h in enumerate(raw_hd):
                prefix = f"calendar.holidays[{i}]"
                if not isinstance(h, dict):
                    errors.append(f"{prefix}: オブジェクトである必要があります")
                    continue
                raw_date = h.get("date")
                d_str = raw_date.isoformat() if isinstance(raw_date, (datetime.date, datetime.datetime)) else str(raw_date) if raw_date is not None else None
                if d_str is None or not is_valid_date(d_str):
                    errors.append(
                        f"{prefix}.date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: {raw_date})"
                    )
                elif d_str in seen_dates:
                    errors.append(f'{prefix}.date: "{d_str}" は重複しています')
                else:
                    seen_dates.add(d_str)

                name = ""
                if "name" in h:
                    # 仕様上、name は文字列またはキー未指定（省略）のみ許可し、
                    # 明示的な null は型不正として拒否する仕様意図（001-yaml-schema.md に準拠）
                    if not isinstance(h["name"], str):
                        errors.append(f"{prefix}.name: 文字列である必要があります")
                    else:
                        name = h["name"]

                holidays.append({"date": d_str, "name": name})

    absences: list[dict[str, Any]] = []
    seen_absences: set[tuple[str, str]] = set()
    if "absences" in cal:
        raw_abs = cal["absences"]
        if raw_abs is None or not isinstance(raw_abs, list):
            errors.append("calendar.absences: 配列である必要があります")
        else:
            for i, a in enumerate(raw_abs):
                prefix = f"calendar.absences[{i}]"
                if not isinstance(a, dict):
                    errors.append(f"{prefix}: オブジェクトである必要があります")
                    continue
                m_id = a.get("member_id")
                if not isinstance(m_id, str) or not m_id:
                    errors.append(f"{prefix}.member_id: 必須の文字列です")

                raw_date = a.get("date")
                d_str = (
                    raw_date.isoformat()
                    if isinstance(raw_date, (datetime.date, datetime.datetime))
                    else str(raw_date)
                    if raw_date is not None
                    else None
                )
                if d_str is None or not is_valid_date(d_str):
                    errors.append(
                        f"{prefix}.date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: {raw_date})"
                    )
                elif m_id and (m_id, d_str) in seen_absences:
                    errors.append(f'{prefix}: メンバ "{m_id}" の日付 "{d_str}" の不在が重複しています')
                elif m_id and d_str:
                    seen_absences.add((m_id, d_str))

                name = ""
                if "name" in a:
                    if not isinstance(a["name"], str):
                        errors.append(f"{prefix}.name: 文字列である必要があります")
                    else:
                        name = a["name"]

                absences.append({"member_id": m_id, "date": d_str, "name": name})

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        data={"workdays": workdays, "holidays": holidays, "absences": absences},
    )


def validate_logical_integrity(
    members: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    calendar: dict[str, Any] | None = None,
    actuals: dict[str, Any] | None = None,
) -> ValidationResult:
    """タスク依存関係・循環参照・スキル充足・実績・不在等の論理整合性を検証する."""
    errors: list[str] = []
    if not isinstance(tasks, list):
        return ValidationResult(valid=True, errors=[])

    task_map: dict[str, tuple[int, dict[str, Any]]] = {}
    for i, t in enumerate(tasks):
        if isinstance(t, dict) and isinstance(t.get("id"), str):
            task_map[t["id"]] = (i, t)

    # 1. 未定義タスク参照チェック (Undefined Task Reference)
    for i, t in enumerate(tasks):
        if not isinstance(t, dict) or not isinstance(t.get("depends_on"), list):
            continue
        for d, dep_id in enumerate(t["depends_on"]):
            if dep_id not in task_map:
                errors.append(
                    f'tasks[{i}].depends_on[{d}]: 未定義のタスク "{dep_id}" を参照しています '
                    f'(参照元: "{t.get("id")}")。解決のヒント: 存在するタスク ID を指定するか、tasks.yaml にタスクを追加してください'
                )

    # 2. 循環依存検知 (DFS Cycle Detection)
    visited: dict[str, int] = {}
    reported_cycles: set[tuple[str, ...]] = set()

    def dfs(task_id: str, path: list[str]) -> None:
        visited[task_id] = 1
        path.append(task_id)

        entry = task_map.get(task_id)
        if entry:
            depends_on = entry[1].get("depends_on")
            if isinstance(depends_on, list):
                for next_id in depends_on:
                    if next_id not in task_map:
                        continue
                    state = visited.get(next_id, 0)
                    if state == 1:
                        cycle_start = path.index(next_id)
                        cycle_nodes = path[cycle_start:]
                        cycle_path = " -> ".join([*cycle_nodes, next_id])
                        cycle_key = tuple(sorted(cycle_nodes))
                        if cycle_key not in reported_cycles:
                            reported_cycles.add(cycle_key)
                            task_index = entry[0]
                            errors.append(
                                f"tasks[{task_index}].depends_on: タスク依存関係に循環参照が検出されました: {cycle_path}。"
                                f"解決のヒント: 先行・後続の依存関係を見直して循環を解消してください"
                            )
                    elif state == 0:
                        dfs(next_id, path)

        path.pop()
        visited[task_id] = 2

    for task_id in list(task_map.keys()):
        if visited.get(task_id, 0) == 0:
            dfs(task_id, [])

    # 3. 未定義スキル参照チェック (Undefined Skill Reference)
    member_ids: set[str] = set()
    if isinstance(members, list):
        member_ids = {
            m["id"]
            for m in members
            if isinstance(m, dict) and isinstance(m.get("id"), str)
        }
        member_skill_sets = [
            set(m.get("skills", []))
            for m in members
            if isinstance(m, dict) and isinstance(m.get("skills"), list)
        ]

        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                continue
            raw_req = t.get("required_skills")
            if not isinstance(raw_req, list) or not raw_req:
                continue
            req_skills = [s for s in raw_req if isinstance(s, str)]
            if not req_skills:
                continue

            req_set = set(req_skills)
            has_capable = any(req_set.issubset(s_set) for s_set in member_skill_sets)

            if not has_capable:
                skills_str = ", ".join(req_skills)
                errors.append(
                    f'tasks[{i}].required_skills: タスク "{t.get("id")}" の必須スキル [{skills_str}] '
                    f"をすべて保有するメンバが存在しません。解決のヒント: members.yaml の skills にスキルを追加するか、タスクの必須スキルを見直してください"
                )

    # 4. カレンダー個別不在の整合性チェック (Calendar Absences)
    absent_member_dates: set[tuple[str, str]] = set()
    if calendar and isinstance(calendar, dict) and isinstance(calendar.get("absences"), list):
        for i, a in enumerate(calendar["absences"]):
            if not isinstance(a, dict):
                continue
            m_id = a.get("member_id")
            d = a.get("date")
            if m_id and m_id not in member_ids:
                errors.append(
                    f'calendar.absences[{i}].member_id: 未定義のメンバ "{m_id}" を参照しています。'
                    f"解決のヒント: members.yaml にメンバを定義してください"
                )
            if m_id and d:
                absent_member_dates.add((m_id, d))

    # 5. 実績工数・タスク進捗の論理整合性チェック (Actuals)
    if actuals and isinstance(actuals, dict):
        work_logs = actuals.get("work_logs", [])
        task_progress = actuals.get("task_progress", [])

        daily_hours: dict[tuple[str, str], float] = {}
        daily_hours_entries: dict[tuple[str, str], list[int]] = {}
        task_members: dict[str, set[str]] = {}
        task_member_entries: dict[str, list[tuple[str, int]]] = {}

        if isinstance(work_logs, list):
            for i, wl in enumerate(work_logs):
                if not isinstance(wl, dict):
                    continue
                m_id = wl.get("member_id")
                t_id = wl.get("task_id")
                d = wl.get("date")
                h = wl.get("hours")

                if m_id and m_id not in member_ids:
                    errors.append(
                        f'actuals.work_logs[{i}].member_id: 未定義のメンバ "{m_id}" を参照しています。'
                        f"解決のヒント: members.yaml にメンバを定義してください"
                    )

                if t_id and t_id not in task_map:
                    errors.append(
                        f'actuals.work_logs[{i}].task_id: 未定義のタスク "{t_id}" を参照しています。'
                        f"解決のヒント: tasks.yaml にタスクを定義してください"
                    )

                if m_id and t_id:
                    task_members.setdefault(t_id, set()).add(m_id)
                    task_member_entries.setdefault(t_id, []).append((m_id, i))

                if m_id and d and isinstance(h, (int, float)) and not isinstance(h, bool):
                    daily_hours[(m_id, d)] = round(daily_hours.get((m_id, d), 0.0) + float(h), 6)
                    daily_hours_entries.setdefault((m_id, d), []).append(i)

                # 不在日との矛盾チェック
                if m_id and d and (m_id, d) in absent_member_dates:
                    errors.append(
                        f'actuals.work_logs[{i}]: メンバ "{m_id}" は日付 "{d}" に不在として登録されていますが、実績工数が記録されています。'
                        f"解決のヒント: 不在日または実績記録を見直してください"
                    )

        # 24h 超過チェック
        for (m_id, d), total_h in sorted(daily_hours.items()):
            if total_h > 24.0:
                last_i = daily_hours_entries[(m_id, d)][-1]
                errors.append(
                    f'actuals.work_logs[{last_i}]: メンバ "{m_id}" の日付 "{d}" の実績工数合計 ({round(total_h, 1)}h) が 24h を超えています。'
                    f"解決のヒント: 実績工数の入力値を確認してください"
                )

        # 1タスク1担当者原則チェック
        for t_id, m_set in sorted(task_members.items()):
            if len(m_set) > 1:
                m_list = ", ".join(sorted(m_set))
                first_member = task_member_entries[t_id][0][0]
                conflict_i = next(idx for mem, idx in task_member_entries[t_id] if mem != first_member)
                errors.append(
                    f'actuals.work_logs[{conflict_i}]: タスク "{t_id}" に複数の担当メンバ ({m_list}) の実績が記録されています。'
                    f"Taskweave では1タスク1担当者原則に基づき、同一タスクへの複数メンバの実績記録は許可されません"
                )

        # task_progress checks
        if isinstance(task_progress, list):
            for i, tp in enumerate(task_progress):
                if not isinstance(tp, dict):
                    continue
                t_id = tp.get("task_id")
                if t_id and t_id not in task_map:
                    errors.append(
                        f'actuals.task_progress[{i}].task_id: 未定義のタスク "{t_id}" を参照しています。'
                        f"解決のヒント: tasks.yaml にタスクを定義してください"
                    )

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def resolve_task_progress(
    tasks: list[dict[str, Any]],
    actuals: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """タスク一覧と実績データから各タスクの残工数および進捗ステータスを解決する (FR-8).

    - task_progress に明示指定されているタスク:
        指定された remaining_hours, status をそのまま採用する.
    - task_progress に未指定のタスク:
        - total_logged_hours: 当該タスクの work_logs の hours 合計
        - remaining_hours: max(0.0, round(estimate_hours - total_logged_hours, 1))
        - status:
            - remaining_hours == 0.0 の場合: "completed"
            - total_logged_hours > 0 の場合: "in_progress"
            - それ以外 (実績なし): "not_started"

    Returns:
        list[dict[str, Any]]: 各タスクの解決済み進捗情報リスト
    """
    work_logs = (actuals.get("work_logs") or []) if isinstance(actuals, dict) else []
    task_progress = (actuals.get("task_progress") or []) if isinstance(actuals, dict) else []

    logged_hours_by_task: dict[str, float] = {}
    if isinstance(work_logs, list):
        for wl in work_logs:
            if isinstance(wl, dict):
                t_id = wl.get("task_id")
                h = wl.get("hours")
                if isinstance(t_id, str) and isinstance(h, (int, float)) and not isinstance(h, bool):
                    logged_hours_by_task[t_id] = round(logged_hours_by_task.get(t_id, 0.0) + float(h), 6)

    explicit_progress: dict[str, dict[str, Any]] = {}
    if isinstance(task_progress, list):
        for tp in task_progress:
            if isinstance(tp, dict):
                t_id = tp.get("task_id")
                if isinstance(t_id, str):
                    explicit_progress[t_id] = tp

    resolved: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            continue
        t_id = task["id"]
        est = float(task.get("estimate_hours", 0.0))
        total_logged = round(logged_hours_by_task.get(t_id, 0.0), 1)

        if t_id in explicit_progress:
            tp = explicit_progress[t_id]
            resolved.append({
                "task_id": t_id,
                "estimate_hours": est,
                "total_logged_hours": total_logged,
                "remaining_hours": float(tp.get("remaining_hours", 0.0)),
                "status": tp.get("status", "not_started"),
            })
        else:
            rem = round(max(0.0, est - total_logged), 1)
            if rem == 0.0:
                status = "completed"
            elif total_logged > 0:
                status = "in_progress"
            else:
                status = "not_started"

            resolved.append({
                "task_id": t_id,
                "estimate_hours": est,
                "total_logged_hours": total_logged,
                "remaining_hours": rem,
                "status": status,
            })

    return resolved


def validate_project_data(dir_path: str | Path) -> ProjectValidationResult:
    """プロジェクト原本 YAML ディレクトリから members, tasks, calendar, actuals を読み込んで一括検証する."""
    p = Path(dir_path)
    errors: list[str] = []
    all_valid = True

    members_data = None
    tasks_data = None
    calendar_data = None
    actuals_data = None
    resolved_progress = None

    # members.yaml
    members_path = p / "members.yaml"
    try:
        content = members_path.read_text(encoding="utf-8")
        res = validate_members(content)
        if not res.valid:
            all_valid = False
            errors.extend(res.errors)
        members_data = res.data
    except Exception as err:
        all_valid = False
        errors.append(f"members.yaml 読み込み失敗: {err}")

    # tasks.yaml
    tasks_path = p / "tasks.yaml"
    try:
        content = tasks_path.read_text(encoding="utf-8")
        res = validate_tasks(content)
        if not res.valid:
            all_valid = False
            errors.extend(res.errors)
        tasks_data = res.data
    except Exception as err:
        all_valid = False
        errors.append(f"tasks.yaml 読み込み失敗: {err}")

    # calendar.yaml
    calendar_path = p / "calendar.yaml"
    try:
        content = calendar_path.read_text(encoding="utf-8")
        res = validate_calendar(content)
        if not res.valid:
            all_valid = False
            errors.extend(res.errors)
        calendar_data = res.data
    except Exception as err:
        all_valid = False
        errors.append(f"calendar.yaml 読み込み失敗: {err}")

    # actuals.yaml (オプショナル)
    actuals_path = p / "actuals.yaml"
    if actuals_path.exists():
        try:
            content = actuals_path.read_text(encoding="utf-8")
            res = validate_actuals(content)
            if not res.valid:
                all_valid = False
                errors.extend(res.errors)
            actuals_data = res.data
        except Exception as err:
            all_valid = False
            errors.append(f"actuals.yaml 読み込み失敗: {err}")

    if all_valid and members_data is not None and tasks_data is not None and calendar_data is not None:
        logical_res = validate_logical_integrity(
            members_data, tasks_data, calendar_data, actuals=actuals_data
        )
        if not logical_res.valid:
            all_valid = False
            errors.extend(logical_res.errors)
        else:
            resolved_progress = resolve_task_progress(tasks_data, actuals=actuals_data)

    return ProjectValidationResult(
        valid=all_valid and len(errors) == 0,
        errors=errors,
        members=members_data,
        tasks=tasks_data,
        calendar=calendar_data,
        actuals=actuals_data,
        resolved_progress=resolved_progress,
    )


def validate_schedule_inputs(
    members_data: list[dict[str, Any]],
    tasks_data: list[dict[str, Any]],
    calendar_data: dict[str, Any],
) -> None:
    """スケジューリング計算前の入力データ整合性を検証する.

    不正な入力が検出された場合は ValueError を送出する.
    """
    # カレンダーの稼働曜日検証
    workdays_cfg = calendar_data.get("workdays", ["mon", "tue", "wed", "thu", "fri"])
    allowed_weekdays = {w for w in workdays_cfg if w in VALID_WORKDAYS}
    if not allowed_weekdays:
        raise ValueError("calendar.workdays に有効な稼働曜日が指定されていません。")

    # 祝日設定の検証
    holidays_cfg = calendar_data.get("holidays", [])
    if isinstance(holidays_cfg, list):
        for h in holidays_cfg:
            if not isinstance(h, dict) or "date" not in h or h["date"] is None:
                raise ValueError(f"calendar.holidays の各項目には 'date' フィールドが必須です: {h}")

    members = {m["id"]: m for m in members_data if isinstance(m, dict) and "id" in m}
    tasks = {t["id"]: t for t in tasks_data if isinstance(t, dict) and "id" in t}

    # タスク工数の最小単位・0.1h刻み検証、未定義依存タスクの検証 (FR-10)、および必須スキル充足メンバの検証 (FR-4)
    for t_id, task in tasks.items():
        est = task.get("estimate_hours", 0)
        if not is_valid_estimate_hours(est):
            raise ValueError(
                f"タスク '{t_id}' の見積工数 ({est}h) は 0.1h 以上の 0.1h 刻み（小数点第1位まで）である必要があります。"
            )
        for dep_id in task.get("depends_on", []):
            if dep_id not in tasks:
                raise ValueError(
                    f"タスク '{t_id}' の先行タスク '{dep_id}' が tasks に定義されていません。"
                )
        if "required_skills" in task:
            raw_skills = task["required_skills"]
            if (
                raw_skills is None
                or not isinstance(raw_skills, list)
                or any(not isinstance(s, str) for s in raw_skills)
            ):
                raise ValueError(
                    f"タスク '{t_id}' の required_skills は文字列のリストである必要があります（null は不可）。"
                )
            req_skills = set(raw_skills)
        else:
            req_skills = set()

        if req_skills:
            capable_members = [
                m_id
                for m_id, member in members.items()
                if req_skills.issubset(set(member.get("skills") or []))
            ]
            if not capable_members:
                raise ValueError(
                    f"タスク '{t_id}' の必須スキル {sorted(req_skills)} をすべて保有するメンバが members に存在しません。"
                )


