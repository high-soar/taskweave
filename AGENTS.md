# Project Agent Guidelines

Welcome to `dev-template`. This repository serves as a base development environment template supporting both **Google Antigravity** and **GitHub Copilot**.

## 1. Environment & Architecture

- **Environment**: VS Code DevContainer (Debian/Ubuntu based)
- **Runtimes**: Node.js 24, npm
- **CLI Tools**: GitHub CLI (`gh`), GitHub Copilot CLI (`@github/copilot`), ripgrep (`rg`)
- **AI Tooling**: Google Antigravity extension, GitHub Copilot Chat

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

- **Coding Conventions**: Follow standard clean-code principles, TypeScript/JavaScript best practices where applicable.
- **Git Commits**: Use descriptive commit messages following Conventional Commits (e.g., `feat: ...`, `fix: ...`, `chore: ...`).
- **Configuration Maintenance**: When modifying or adding configurations (`.devcontainer/`, `.agents/`, `.github/`, `AGENTS.md`), always consult the **`repo-config-management`** skill.
