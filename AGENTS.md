# Taskweave Project Agent Guidelines

Taskweave is a schedule-planning tool for coding agents. It is intended to manage members, tasks, estimates, constraints, and actual work as text-based source files so that an agent can help propose and revise a team schedule.

The repository is currently in the requirements and tool-selection phase. The scheduling model, source-file schema, and application commands are not finalized yet.

## 1. Environment & Architecture

- **Environment**: VS Code DevContainer (Debian/Ubuntu based)
- **Runtimes**: Node.js 24, npm, `uv`
- **CLI Tools**: GitHub CLI (`gh`), GitHub Copilot CLI (`@github/copilot`), ripgrep (`rg`)
- **AI Tooling**: Google Antigravity extension, GitHub Copilot Chat
- **Application status**: The Python scheduling engine and its dependencies have not been added yet.

When implementation starts, keep source data separate from generated schedules. Preserve the distinction between estimates, planned work, and actual work so that replanning from a chosen point in time remains possible.

---

## 2. AI Configuration & SSOT (Single Source of Truth) Architecture

To avoid duplication across AI assistants, this repository follows a unified configuration strategy:

| Component                | Source of Truth (SSOT)           | Antigravity Integration             | GitHub Copilot Integration                       |
| :----------------------- | :------------------------------- | :---------------------------------- | :----------------------------------------------- |
| **Rules / Instructions** | `AGENTS.md` (this file)          | Natively loaded from workspace root | Referenced via `.github/copilot-instructions.md` |
| **Skills**               | `.github/skills/<name>/SKILL.md` | Mapped via `.agents/skills.json`    | Natively loaded from `.github/skills/`           |
| **Custom Agents**        | `.github/agents/<name>.agent.md` | Accessible as agent templates/rules | Natively loaded from `.github/agents/`           |

---

## 3. General Development Rules

- **Domain model**: Treat member capacity, skills, task estimates, dependencies, deadlines, absences, and actual work as separate concepts. Do not collapse actual work into a revised estimate.
- **Source of truth**: Prefer text-based source files for planning data. Generated plans and diagnostics must be reproducible and must not silently replace the source data.
- **Current phase**: Do not present a proposed data schema or calculation behavior as implemented until it has been agreed, tested, and documented.
- **Coding Conventions**: Follow standard clean-code principles and the established conventions of each language. Keep Node.js tooling and future Python tooling independently understandable.
- **Validation**: Add focused tests for scheduling constraints and replanning behavior when the implementation begins. Changes to source-file formats require validation and documentation updates.
- **Git Commits**: Use descriptive commit messages following Conventional Commits (e.g., `feat: ...`, `fix: ...`, `chore: ...`).
- **Configuration Maintenance**: When modifying or adding configurations (`.devcontainer/`, `.agents/`, `.github/`, `AGENTS.md`), always consult the **`repo-config-management`** skill.
