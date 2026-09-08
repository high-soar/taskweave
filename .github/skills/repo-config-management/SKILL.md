---
name: repo-config-management
description: Use this skill when modifying, adding, or maintaining repository configurations, including .devcontainer/, .agents/, .github/, .githooks/, AGENTS.md, skills, agents, Git hooks, or AI tool coexistence settings.
---

# Repository Configuration & AI Coexistence Management

This skill defines the operational standards and procedures for maintaining configurations in this repository, ensuring seamless coexistence between **Google Antigravity** and **GitHub Copilot** with a Single Source of Truth (SSOT).

---

## 1. Architecture Overview (SSOT Policy)

To avoid configuration drift and duplication:

- **Never duplicate instructions or skill definitions across different directories.**
- Place all shared definitions in standard directories and use reference configurations (`skills.json`, markdown links).

```text
/
├── AGENTS.md                             # [SSOT] Project rules, environment context, general agent behavior
├── .agents/
│   └── skills.json                       # [Mapping] Configures Antigravity to load skills from .github/skills
├── .githooks/
│   └── <hook-name>                        # [Tracked] Repository-shared Git hook scripts
└── .github/
    ├── copilot-instructions.md           # [Bridge] Copilot instruction wrapper pointing to AGENTS.md
    ├── agents/
    │   └── *.agent.md                    # [SSOT] Custom Agent & Persona definitions
    └── skills/
        └── <skill-name>/
            ├── SKILL.md                  # [SSOT] Skill instructions with YAML frontmatter
            ├── scripts/                  # (Optional) Helper scripts
            └── references/               # (Optional) Extended reference documents
```

---

## 2. Configuration Maintenance Procedures

### A. Modifying or Adding Project Rules / Instructions

1. **Target File**: `AGENTS.md` (Repository root).
2. **Action**: Edit `AGENTS.md` directly.
3. **Verification**:
   - Ensure instructions are tool-agnostic (avoid hardcoding tool-exclusive prompt commands unless specified).
   - Verify that `.github/copilot-instructions.md` still properly references `AGENTS.md`.

### B. Adding a New Skill

1. **Target Directory**: `.github/skills/<new-skill-name>/`
2. **File Requirement**: Create `SKILL.md` with standard YAML frontmatter:
   ```markdown
   ---
   name: <new-skill-name>
   description: Use this skill when [specific trigger conditions and task description].
   ---

   # Skill Title

   ## Procedures

   1. Step 1...
   2. Step 2...
   ```
3. **Verification**:
   - Ensure `.agents/skills.json` contains `{"path": ".github/skills"}` (Antigravity automatically discovers the new skill).
   - Validate YAML frontmatter syntax.
   - Use relative links for helper scripts or references in the same skill folder.

### C. Adding or Modifying a Custom Agent / Subagent Persona

1. **Target Directory**: `.github/agents/`
2. **File Requirement**: Create `<agent-name>.agent.md` with role definition, persona, guidelines, and tool associations.
3. **Verification**:
   - Verify that the agent instructions align with `AGENTS.md`.
   - If a corresponding skill is required, create it under `.github/skills/`.

### D. Modifying DevContainer or Tooling Settings

1. **Target Files**:
   - `.devcontainer/devcontainer.json`
   - `.devcontainer/Dockerfile`
2. **Action Checklist**:
   - If new global tools or extensions are added, update `devcontainer.json`.
   - If AI mounts or volume names change, ensure both Antigravity history and Copilot history volumes remain configured.
   - Update `AGENTS.md` Environment & Architecture section if tool versions or system dependencies change.

---

### E. Adding or Modifying Repository Git Hooks

1. **Target Files**:
   - `.githooks/<hook-name>` for tracked hook scripts.
   - `package.json` for the `prepare` lifecycle entry.
   - `scripts/setup-git-hooks.mjs` for local hook-path activation.
2. **Action Checklist**:
   - Keep the shared hook script under `.githooks/`; do not use `.git/hooks/` as the source of truth.
   - Configure each clone with `git config --local core.hooksPath .githooks` through an idempotent setup script.
   - Preserve the executable bit on every hook script.
   - Make the setup script skip cleanly when it is run outside a Git repository.
3. **Verification**:
   - Run `npm run prepare` and confirm `git config --local --get core.hooksPath` returns `.githooks`.
   - Run `git hook run <hook-name>` and confirm the hook's quality check succeeds.

## 3. Verification Checklist

Whenever configuration changes are made:

- [ ] **JSON Syntax**: Ensure all `.json` files (`devcontainer.json`, `.agents/skills.json`, etc.) are valid JSON.
- [ ] **Markdown Links**: Check that links between files (e.g. `[AGENTS.md](../AGENTS.md)`) resolve correctly.
- [ ] **No Duplicate Originals**: Confirm no redundant skill files exist under `.agents/skills/` (everything lives in `.github/skills/`).
- [ ] **Git Hooks**: Confirm tracked hooks live under `.githooks/`, retain executable permissions, and are activated through the local `core.hooksPath` setting.
