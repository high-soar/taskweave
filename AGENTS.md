---
type: agent-guidelines
title: Taskweave Project Agent Guidelines
description: Taskweave のエージェントと開発者が共有するプロジェクト運用指針
tags: [ai-agents, development, project-rules]
status: stable
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-25T02:25:00Z }
---

# Taskweave Project Agent Guidelines

Taskweave is a schedule-planning tool for coding agents. It is intended to manage members, tasks, estimates, constraints, and actual work as text-based source files so that an agent can help propose and revise a team schedule.

The repository has finalized its source-file schema (Milestone 1), completed the scheduling engine MVP in Python / OR-Tools (Milestone 2, Issues #12, #13, #14, #15, #16), implemented actuals tracking and replanning workflows (Milestone 3, Issues #25, #26, #27, #28), completed full agent CLI commands and reporting (Milestone 4, Issues #40, #41, #42, #43, #45), and completed schema expressiveness and solver optimization (Milestone 5, Issues #38, #50, #51, #52, #53, #54).

## 1. Environment & Architecture

- **Environment**: VS Code DevContainer (Debian/Ubuntu based)
- **Runtimes**: Node.js 24, npm, `uv`
- **CLI Tools**: GitHub CLI (`gh`), GitHub Copilot CLI (`@github/copilot`), ripgrep (`rg`)
- **AI Tooling**: Google Antigravity extension, GitHub Copilot Chat
- **Application status**: The Python scheduling engine, replanning workflows, and full agent CLI commands (`validate`, `plan`, `replan`, `log`, `apply`) with reporting capabilities (Mermaid, Markdown) are implemented in `python/` using OR-Tools CP-SAT and managed via `uv`.

Keep source data separate from generated schedules. Preserve the distinction between estimates, planned work, and actual work so that replanning from a chosen point in time remains possible.

---

## 2. AI Configuration & SSOT (Single Source of Truth) Architecture

To avoid duplication across AI assistants, this repository follows a unified configuration strategy:

| Component                   | Source of Truth (SSOT)                                   | Antigravity Integration                                                                                                  | GitHub Copilot Integration                       |
| :-------------------------- | :------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------- |
| **Rules / Instructions**    | `AGENTS.md` (this file)                                  | Natively loaded from workspace root                                                                                      | Referenced via `.github/copilot-instructions.md` |
| **Human development rules** | [`docs/development/rules.md`](docs/development/rules.md) | Linked from this file                                                                                                    | Linked from `README.md` and this file            |
| **Skills**                  | `.github/skills/<name>/SKILL.md`                         | Mapped via `.agents/skills.json`                                                                                         | Natively loaded from `.github/skills/`           |
| **Custom Agents**           | `.github/agents/<name>.agent.md`                         | Accessible as agent templates/rules (`taskweave-maintainer`: 構成・環境保守, `pr-reviewer`: PR プレレビュー・再レビュー) | Natively loaded from `.github/agents/`           |

---

## 3. General Development Rules

- **Domain model**: Treat member capacity, skills, task estimates, dependencies, deadlines, absences, and actual work as separate concepts. Do not collapse actual work into a revised estimate.
- **Source of truth**: Prefer text-based source files for planning data. Generated plans and diagnostics must be reproducible and must not silently replace the source data.
- **Current phase**: Do not present a proposed data schema or calculation behavior as implemented until it has been agreed, tested, and documented.
- **Coding Conventions**: Follow standard clean-code principles and the established conventions of each language. Keep Node.js tooling and future Python tooling independently understandable.
- **Human development workflow**: The rules for SDD/TDD, Issue tracking, DoR/DoD, Git commits, PR review, and branch/worktree operation are defined in [`docs/development/rules.md`](docs/development/rules.md). Follow that document and do not duplicate its details here.
- **GitHub CLI (`gh`) Integration**: Use `gh issue list`, `gh issue view`, and `gh issue create` to inspect and interact with the backlog from the CLI environment.
- **Validation**: Add focused tests for scheduling constraints and replanning behavior when the implementation begins. Changes to source-file formats require validation and documentation updates.
- **Configuration Maintenance**: When modifying or adding configurations (`.devcontainer/`, `.agents/`, `.github/`, `AGENTS.md`), always consult the **`repo-config-management`** skill.
- **PR Review & Merge Guardrail**: Pull Request の最終承認およびマージは人間（開発者）の権限です。エージェントは PR 作成、CI 正常終了確認、独立サブエージェント（`pr-reviewer`）によるプレレビューおよび再レビュー完了確認までを担当し、ユーザーから明示的な指示がない限り、自律的に PR をマージしてはなりません。

## 4. Human Development Rules

人が開発するときのルールは [`docs/development/rules.md`](docs/development/rules.md) を正本とします。エージェントが Issue、仕様、テスト、レビュー、Git 運用に関わる場合もこの文書に従い、ここへ同じ手順を重複して記載しません。
