---
name: sdd-tdd
description: Use this skill when designing, adding, or modifying features, data schemas, or calculation logic in Taskweave following Spec-Driven Development (SDD) and Test-Driven Development (TDD). Also use whenever the user requests implementing new functionality, designing YAML schemas, writing tests first, or refactoring with tests.
---

# Spec-Driven Development (SDD) & Test-Driven Development (TDD)

This skill guides AI agents and developers in applying **Spec-Driven Development (SDD)** and **Test-Driven Development (TDD)** in the Taskweave project.

---

## 1. Core Principles

- **Value-Driven User Stories**: Every non-trivial change should trace back to a User Story Issue (labeled `user-story`) aligned with `ROADMAP.md`.
- **Definition of Ready (DoR)**: Do not begin coding until the story's Who/What/Why, Acceptance Criteria, and corresponding specification are clearly defined.
- **No Implementation Without a Spec**: Code and calculation logic must not be implemented until the corresponding specification and data schema are reviewed and accepted in `specs/`.
- **Red-Green-Refactor**: Always write failing tests first (Red), implement the minimum code to pass them (Green), and then clean up the design (Refactor).
- **YAGNI & Minimal Code**: Leverage the `ponytail` skill during the Green phase. Write only the minimal code needed to pass the tests—do not add speculative features or unnecessary abstractions.
- **Definition of Done (DoD)**: Verify all acceptance criteria tests pass, quality gates are green, and documentation is updated before closing the story.

---

## 2. Five-Phase Workflow

### Phase 0: User Story & DoR Check

1. **Identify or Create Story**:
   - Inspect existing issues: `gh issue list --label user-story`.
   - If starting a new capability, create a User Story Issue from the template ([`.github/ISSUE_TEMPLATE/user_story.yml`](../../../.github/ISSUE_TEMPLATE/user_story.yml)).
2. **Verify DoR**:
   - Confirm Who/What/Why is clear.
   - Confirm Acceptance Criteria (testable scenarios) are listed.
   - Track progress using the Tasklist (`- [ ]`) in the story Issue.

### Phase 1: Specification (SDD & OKF)

1. **Check Existing Specs**: Inspect [`specs/`](../../../specs/) to see if an existing specification covers the target change.
2. **Consult OKF Skill**:
   - Always load and follow the **`okf`** skill ([`../okf/SKILL.md`](../okf/SKILL.md)) for YAML frontmatter rules, actor conventions, and progressive disclosure.
3. **Draft or Update Spec**:
   - Copy [`specs/templates/spec-template.md`](../../../specs/templates/spec-template.md) to `specs/<number>-<slug>.md`.
   - Set OKF frontmatter:
     - `type: spec`
     - `status: draft`
     - `issues: [<issue_number>, ...]` (または単一の場合 `issue: <issue_number>`)
     - `generated: { by: <agent_actor>, at: <ISO_8601_UTC> }`
   - Clearly document:
     - User story, Functional & Non-Functional Requirements.
     - Data structures & YAML schemas (Schema-Driven).
     - Concrete Acceptance Criteria (Given-When-Then scenarios).
     - Constraints and explicit Out-of-Scope boundaries.
4. **User Alignment & Approval**:
   - Review the spec with the user.
   - Once agreed, update the specification:
     - `status: accepted`
     - `verified: { by: human:<user_id>, at: <ISO_8601_UTC> }` (記録して人間の承認を明示)

### Phase 2: Test First (TDD - Red)

1. **Translate Acceptance Criteria to Tests**:
   - Each scenario from the spec must correspond to one or more focused tests.
   - **Current Node.js / Infra tools**: Place tests under `test/` using Node's built-in test runner (`node:test`).
   - **Future Python Calculation Engine**: Place tests under `tests/` using `pytest`.
2. **Run Tests to Verify Failure**:
   - Execute the test runner (e.g. `npm test` or `pytest`).
   - Confirm that tests fail specifically due to missing functionality (Red), not due to syntax errors or missing imports.

### Phase 3: Minimum Implementation (TDD - Green)

1. **Write Minimal Code**:
   - Write only the simplest, most direct code that makes the failing tests pass.
   - Do not anticipate hypothetical future requirements (YAGNI).
2. **Verify Green**:
   - Re-run the tests and confirm that all test cases pass cleanly.

### Phase 4: Refactor & DoD (TDD - Refactor)

1. **Clean Up**:
   - Improve code structure, variable naming, and readability while keeping all tests passing.
   - Remove duplicate logic or temporary scaffolding.
2. **Run Full Quality Gate**:
   - Run format check, lint, tests, and typecheck:
     ```sh
     npm run format:check
     npm run lint
     npm test
     npm run typecheck
     ```
3. **Verify DoD**:
   - Update the specification document status from `Accepted` to `Implemented`.
   - Check off all completed items in the Issue's Tasklist.

### Phase 5: PR & Independent Pre-Review (AI プレレビュー)

1. **Create Pull Request**:
   - Push the branch and create a PR referencing the issue (`Closes #<issue-number>`).
   - Verify that CI passes.
2. **Invoke Independent `pr-reviewer` Subagent**:
   - Launch `pr-reviewer` independently passing ONLY the PR number or URL.
   - Do NOT pass implementation chat history or bias.
   - The subagent performs a zero-context critical review and posts comments with `[MUST]`, `[SHOULD]`, `Why`, and `Alternative` via `gh pr comment`.
3. **Address Review Feedback**:
   - Inspect review comments (`[R1]`, `[R2]`...).
   - Fix all `[MUST]` and `[SHOULD]` items in code and tests.
   - For deferred items (e.g., non-blocking refactoring, future improvements), **always file a dedicated GitHub Issue** to track it in the backlog, and link the issue number in the PR reply comment.
   - Commit, push, and reply to each `[Rx]` in the PR comments following the standard response format (policy, reason, commit, test result, remaining risk).
4. **Invoke Re-review & Verify Resolution**:
   - Invoke `pr-reviewer` again to perform a re-review of the updated diff.
   - Verify that all review items are marked as `RESOLVED` (fixed or properly tracked via an open GitHub Issue). If any `UNRESOLVED` items remain, repeat the fix/issue cycle.
5. **Handoff to Human Review**:
   - Once all items are `RESOLVED` and CI passes, notify the human developer for final review, approval, and merge.

---

## 3. Verification Checklist

- [ ] User Story Issue exists with defined Who/What/Why and Acceptance Criteria (DoR satisfied).
- [ ] A specification document exists in `specs/` with status `Accepted` or `Implemented`.
- [ ] Acceptance criteria in the spec are covered by unit or integration tests.
- [ ] Tests were confirmed failing (Red) prior to implementation.
- [ ] Implementation satisfies all tests with no extraneous code (Green + YAGNI).
- [ ] All quality checks (`format:check`, `lint`, `test`, `typecheck`) pass without errors (DoD satisfied).
- [ ] PR was created and reviewed by independent `pr-reviewer` subagent.
- [ ] All `[MUST]` and `[SHOULD]` review items are addressed and answered in PR comments.
- [ ] Any deferred review items have been filed as dedicated GitHub Issues and linked in PR comments.
- [ ] Re-review by `pr-reviewer` confirmed all review items are `RESOLVED`.
