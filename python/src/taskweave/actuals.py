"""Taskweave 実績工数およびタスク進捗の記録・更新ロジック (actuals)."""

from __future__ import annotations

import copy
import datetime
from pathlib import Path
from typing import Any
import yaml

from taskweave.validator import (
    VALID_TASK_STATUSES,
    is_valid_date,
    is_valid_estimate_hours,
    is_valid_remaining_hours,
    validate_actuals,
    validate_calendar,
    validate_logical_integrity,
    validate_members,
    validate_tasks,
)


def record_work_log(
    dir_path: str | Path,
    date: str,
    member_id: str,
    task_id: str,
    hours: float,
    remaining_hours: float | None = None,
    status: str | None = None,
    handoff_to: str | None = None,
    add: bool = False,
) -> tuple[bool, list[str]]:
    """actuals.yaml に実績工数・進捗を事前検証の上で安全に記録する.

    Args:
        dir_path: 原本 YAML が配置されたディレクトリ
        date: 作業日 (YYYY-MM-DD)
        member_id: メンバー ID
        task_id: タスク ID
        hours: 稼働工数 (0.1刻み正の数値)
        remaining_hours: 残工数 (省略可)
        status: タスクステータス (省略可)
        handoff_to: 引き継ぎ先メンバー ID (省略可)
        add: 同一日の同一メンバ・同一タスク実績が既にある場合に加算するか (デフォルト: 上書き)

    Returns:
        tuple[bool, list[str]]: (成功フラグ, エラーメッセージリスト)
    """
    directory = Path(dir_path).resolve()
    errors: list[str] = []

    # 1. 引数の基本バリデーション
    if not is_valid_date(date):
        errors.append(f"date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: {date})")

    if not is_valid_estimate_hours(hours):
        errors.append(
            f"hours: 0.1 以上の 0.1 時間刻み（小数点以下1桁まで）の正の数値である必要があります (指定値: {hours})"
        )

    if remaining_hours is not None and not is_valid_remaining_hours(remaining_hours):
        errors.append(
            f"remaining_hours: 0.0 以上の 0.1 時間刻み（小数点以下1桁まで）の数値である必要があります (指定値: {remaining_hours})"
        )

    if status is not None and status not in VALID_TASK_STATUSES:
        errors.append(
            f"status: 有効なステータス ({', '.join(sorted(VALID_TASK_STATUSES))}) である必要があります (指定値: {status})"
        )

    if handoff_to is not None and (not isinstance(handoff_to, str) or not handoff_to.strip()):
        errors.append("handoff_to: 非空の文字列である必要があります")

    if errors:
        return False, errors

    # 2. 原本 YAML (members, tasks, calendar) の読み込み・検証
    files_to_check = [
        ("members.yaml", validate_members),
        ("tasks.yaml", validate_tasks),
        ("calendar.yaml", validate_calendar),
    ]
    parsed_masters: dict[str, Any] = {}

    for fname, validator_func in files_to_check:
        fpath = directory / fname
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception as err:
            errors.append(f"{fname}: 読み込み失敗: {err}")
            continue

        res = validator_func(content)
        if not res.valid:
            errors.extend(res.errors)
        else:
            parsed_masters[fname] = res.data

    if errors:
        return False, errors

    # 3. 既存 actuals.yaml の読み込みと構造判定
    actuals_path = directory / "actuals.yaml"
    actuals_dict: dict[str, Any] = {}

    if actuals_path.exists():
        try:
            content = actuals_path.read_text(encoding="utf-8")
            raw = yaml.safe_load(content)
        except Exception as err:
            return False, [f"actuals.yaml 読み込み失敗: {err}"]

        if raw is None:
            raw = {}
        elif not isinstance(raw, dict):
            return False, ["actuals: オブジェクトが必須です"]

        if not raw:
            actuals_dict = {}
        elif "actuals" in raw:
            if not isinstance(raw["actuals"], dict):
                return False, ["actuals: オブジェクトが必須です"]
            if "work_logs" in raw or "task_progress" in raw:
                return False, [
                    "actuals.yaml: 'actuals:' ルートキーとトップレベル直下の 'work_logs' または 'task_progress' が同時に存在します"
                ]
            actuals_dict = copy.deepcopy(raw["actuals"])
        else:
            actuals_dict = copy.deepcopy(raw)

    # 4. メモリ上での稼働ログ更新
    work_logs = actuals_dict.setdefault("work_logs", [])
    if not isinstance(work_logs, list):
        return False, ["actuals.work_logs: 配列である必要があります"]

    # 既存の date を文字列に正規化
    for wl in work_logs:
        if isinstance(wl, dict) and "date" in wl:
            d = wl["date"]
            if isinstance(d, (datetime.date, datetime.datetime)):
                wl["date"] = d.isoformat()
            elif d is not None:
                wl["date"] = str(d)

    target_log = None
    for wl in work_logs:
        if (
            isinstance(wl, dict)
            and wl.get("date") == date
            and wl.get("member_id") == member_id
            and wl.get("task_id") == task_id
        ):
            target_log = wl
            break

    h_float = float(hours)
    if target_log is not None:
        if add:
            target_log["hours"] = round(float(target_log.get("hours", 0.0)) + h_float, 1)
        else:
            target_log["hours"] = h_float
    else:
        work_logs.append({
            "date": date,
            "member_id": member_id,
            "task_id": task_id,
            "hours": h_float,
        })

    # 5. メモリ上での進捗更新 (指定時のみ)
    if remaining_hours is not None or status is not None or handoff_to is not None:
        task_progress = actuals_dict.setdefault("task_progress", [])
        if not isinstance(task_progress, list):
            return False, ["actuals.task_progress: 配列である必要があります"]

        target_tp = None
        for tp in task_progress:
            if isinstance(tp, dict) and tp.get("task_id") == task_id:
                target_tp = tp
                break

        if target_tp is not None:
            if remaining_hours is not None:
                target_tp["remaining_hours"] = float(remaining_hours)
            if status is not None:
                target_tp["status"] = status
            if handoff_to is not None:
                target_tp["handoff_to"] = handoff_to
            if target_tp.get("status") == "completed" and remaining_hours is None:
                target_tp["remaining_hours"] = 0.0
            elif target_tp.get("remaining_hours") == 0.0 and status is None:
                target_tp["status"] = "completed"
            elif (
                target_tp.get("remaining_hours", 0.0) > 0.0
                and status is None
                and target_tp.get("status") == "completed"
            ):
                target_tp["status"] = "in_progress"
        else:
            task_info = next(
                (t for t in parsed_masters.get("tasks.yaml", []) if t.get("id") == task_id),
                {},
            )
            est = float(task_info.get("estimate_hours", 0.0))
            logged = sum(
                float(wl.get("hours", 0.0))
                for wl in work_logs
                if isinstance(wl, dict) and wl.get("task_id") == task_id
            )

            if status == "completed" and remaining_hours is None:
                calc_rem = 0.0
                calc_status = "completed"
            elif remaining_hours is not None and float(remaining_hours) == 0.0 and status is None:
                calc_rem = 0.0
                calc_status = "completed"
            else:
                calc_rem = (
                    float(remaining_hours)
                    if remaining_hours is not None
                    else max(0.0, round(est - logged, 1))
                )
                if status is not None:
                    calc_status = status
                else:
                    calc_status = (
                        "completed"
                        if calc_rem == 0.0
                        else "in_progress"
                        if (logged > 0 or calc_rem < est)
                        else "not_started"
                    )

            new_tp: dict[str, Any] = {
                "task_id": task_id,
                "remaining_hours": float(calc_rem),
                "status": calc_status,
            }
            if handoff_to is not None:
                new_tp["handoff_to"] = handoff_to
            task_progress.append(new_tp)

    # 6. 事前スキーマ検証および論理整合性検証（常に actuals: ルートキー付きの正規化形式で書き出す）
    candidate_data = {"actuals": actuals_dict}
    yaml_str = yaml.safe_dump(candidate_data, sort_keys=False, allow_unicode=True)

    act_res = validate_actuals(yaml_str)
    if not act_res.valid:
        return False, act_res.errors

    logical_res = validate_logical_integrity(
        parsed_masters["members.yaml"],
        parsed_masters["tasks.yaml"],
        parsed_masters["calendar.yaml"],
        actuals=act_res.data,
    )
    if not logical_res.valid:
        return False, logical_res.errors

    # 7. ファイルへの書き込み (アトミック書き込み)
    try:
        actuals_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = actuals_path.with_name(f"{actuals_path.name}.tmp.{datetime.datetime.now().timestamp()}")
        tmp_path.write_text(yaml_str, encoding="utf-8")
        tmp_path.replace(actuals_path)
    except Exception as err:
        return False, [f"actuals.yaml 書き込み失敗: {err}"]

    return True, []
