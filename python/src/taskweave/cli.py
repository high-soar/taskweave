"""Taskweave コマンドラインインターフェース (CLI).

コマンド:
- taskweave validate [dir]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any
import yaml

from taskweave.validator import (
    validate_calendar,
    validate_logical_integrity,
    validate_members,
    validate_tasks,
)

FILES = [
    ("members.yaml", validate_members),
    ("tasks.yaml", validate_tasks),
    ("calendar.yaml", validate_calendar),
]


def _get_error_path(error_msg: str) -> list[str | int]:
    match = re.match(
        r"^((?:members|tasks|calendar)(?:\[\d+\])?(?:\.[\w-]+(?:\[\d+\])?)*)\s*:",
        error_msg,
    )
    if not match:
        return []
    parts = match.group(1).replace("[", ".").replace("]", "").split(".")
    result: list[str | int] = []
    for p in parts:
        if p.isdigit():
            result.append(int(p))
        else:
            result.append(p)
    return result


def _get_node_line(node: yaml.Node | None, path: list[str | int]) -> int | None:
    if node is None or not path:
        return (node.start_mark.line + 1) if node and hasattr(node, "start_mark") else None

    current = node
    for part in path:
        if isinstance(part, int):
            if isinstance(current, yaml.SequenceNode) and 0 <= part < len(current.value):
                current = current.value[part]
            else:
                break
        elif isinstance(part, str):
            if isinstance(current, yaml.MappingNode):
                found = None
                for k, v in current.value:
                    if isinstance(k, yaml.ScalarNode) and k.value == part:
                        found = v
                        break
                if found:
                    current = found
                else:
                    break
            else:
                break

    return (current.start_mark.line + 1) if current and hasattr(current, "start_mark") else None


def _get_error_line(doc_node: yaml.Node | None, error_msg: str, parse_err: yaml.YAMLError | None = None) -> int:
    if parse_err is not None and hasattr(parse_err, "problem_mark") and parse_err.problem_mark:
        return parse_err.problem_mark.line + 1

    if doc_node is not None:
        path = _get_error_path(error_msg)
        for length in range(len(path), 0, -1):
            line = _get_node_line(doc_node, path[:length])
            if line is not None:
                return line
        if hasattr(doc_node, "start_mark"):
            return doc_node.start_mark.line + 1

    return 1


def validate_directory(dir_path: str | Path) -> bool:
    """ディレクトリ内の原本 YAML を検証し、エラーがあれば stderr に出力する.

    Returns:
        bool: エラーが存在した場合は True、すべて成功した場合は False
    """
    directory = Path(dir_path).resolve()
    has_errors = False
    parsed_data: dict[str, Any] = {}
    doc_nodes: dict[str, yaml.Node | None] = {}

    for file_name, validator_func in FILES:
        file_path = directory / file_name
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as err:
            has_errors = True
            sys.stderr.write(f"{file_name}:1: 読み込み失敗: {err}\n")
            continue

        parse_err: yaml.YAMLError | None = None
        doc_node: yaml.Node | None = None
        try:
            doc_node = yaml.compose(source)
        except yaml.YAMLError as y_err:
            parse_err = y_err

        doc_nodes[file_name] = doc_node
        res = validator_func(source)

        if not res.valid:
            has_errors = True
            for err in res.errors:
                line = _get_error_line(doc_node, err, parse_err)
                sys.stderr.write(f"{file_name}:{line}: {err}\n")
        else:
            parsed_data[file_name] = res.data

    if (
        not has_errors
        and "members.yaml" in parsed_data
        and "tasks.yaml" in parsed_data
        and "calendar.yaml" in parsed_data
    ):
        logical_res = validate_logical_integrity(
            parsed_data["members.yaml"],
            parsed_data["tasks.yaml"],
            parsed_data["calendar.yaml"],
        )
        if not logical_res.valid:
            has_errors = True
            for err in logical_res.errors:
                target_file = "tasks.yaml"
                if err.startswith("members"):
                    target_file = "members.yaml"
                elif err.startswith("calendar"):
                    target_file = "calendar.yaml"

                line = _get_error_line(doc_nodes.get(target_file), err)
                sys.stderr.write(f"{target_file}:{line}: {err}\n")

    return has_errors


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(prog="taskweave", description="Taskweave CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="サブコマンド")

    # validate サブコマンド
    val_parser = subparsers.add_parser("validate", help="原本 YAML データを検証する")
    val_parser.add_argument(
        "directory",
        nargs="?",
        default="data",
        help="原本 YAML ファイル（members.yaml, tasks.yaml, calendar.yaml）が置かれたディレクトリ (デフォルト: data)",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "validate":
        has_errors = validate_directory(args.directory)
        if has_errors:
            return 1
        target_dir = Path(args.directory).resolve()
        sys.stdout.write(f"YAML 原本データの検証に成功しました: {target_dir}\n")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

