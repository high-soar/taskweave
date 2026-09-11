import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  checkRepository,
  isToolingMarkdown,
  updateIndex,
  validateOkfDocument,
} from "../scripts/okf-docs.mjs";

const execFileAsync = promisify(execFile);

const VALID_FRONTMATTER = `---
type: concept
title: Test document
description: A test document for OKF validation
tags: [documentation, test]
generated: { by: copilot/chat, at: 2026-09-10T11:11:30Z }
---

# Test document
`;

const CLEAN_GIT_ENV = { ...process.env };
delete CLEAN_GIT_ENV.GIT_DIR;
delete CLEAN_GIT_ENV.GIT_WORK_TREE;
delete CLEAN_GIT_ENV.GIT_INDEX_FILE;
delete CLEAN_GIT_ENV.GIT_OBJECT_DIRECTORY;
delete CLEAN_GIT_ENV.GIT_COMMON_DIR;
delete CLEAN_GIT_ENV.GIT_PREFIX;

async function createGitRepository() {
  const directory = await mkdtemp(join(tmpdir(), "taskweave-okf-"));
  await execFileAsync("git", ["init", "--quiet"], {
    cwd: directory,
    env: CLEAN_GIT_ENV,
  });
  return directory;
}

async function trackFiles(directory, files) {
  await execFileAsync("git", ["add", ...files], {
    cwd: directory,
    env: CLEAN_GIT_ENV,
  });
}

async function writeRepositoryFixture(directory) {
  await mkdir(join(directory, ".github/skills/demo"), { recursive: true });
  await writeFile(join(directory, "README.md"), VALID_FRONTMATTER);
  await writeFile(
    join(directory, "index.md"),
    `---
type: index
title: Test index
description: An index for tests
tags: [documentation, index]
generated: { by: copilot/chat, at: 2026-09-10T11:11:30Z }
---

# Test index

Manual introduction.

<!-- BEGIN GENERATED: okf-index -->
<!-- END GENERATED: okf-index -->

Manual conclusion.
`,
  );
  await writeFile(
    join(directory, ".github/skills/demo/SKILL.md"),
    `---
name: demo
description: A tool-specific document
---

# Demo
`,
  );
  await writeFile(
    join(directory, "untracked.md"),
    "This file is intentionally not tracked and has no frontmatter.\n",
  );
  await trackFiles(directory, ["README.md", "index.md", ".github"]);
}

describe("OKF document validation", () => {
  it("validates the fixed frontmatter format", () => {
    const result = validateOkfDocument("README.md", VALID_FRONTMATTER);

    assert.equal(result.valid, true);
    assert.deepEqual(result.diagnostics, []);
    assert.equal(result.data.type, "concept");
    assert.deepEqual(result.data.tags, ["documentation", "test"]);
  });

  it("reports missing frontmatter fields and invalid tags", () => {
    const result = validateOkfDocument(
      "docs/bad.md",
      `---
type: concept
title: Bad document
description: Invalid metadata
tags: [Bad_Tag, test, test]
generated: { by: copilot/chat, at: 2026-09-10T11:11:30Z }
---
`,
    );

    assert.equal(result.valid, false);
    assert.ok(
      result.diagnostics.some((item) => item.message.includes("kebab-case")),
    );
    assert.ok(result.diagnostics.some((item) => item.message.includes("重複")));
  });

  it("reports malformed YAML with a frontmatter line", () => {
    const result = validateOkfDocument(
      "docs/bad.md",
      `---
type: [concept
---
`,
    );

    assert.equal(result.valid, false);
    assert.match(result.diagnostics[0].filePath, /docs\/bad\.md/);
    assert.equal(typeof result.diagnostics[0].line, "number");
    assert.match(result.diagnostics[0].message, /YAML 構文エラー/);
  });

  it("keeps tooling documents outside the OKF aggregation profile", () => {
    assert.equal(isToolingMarkdown(".github/skills/demo/SKILL.md"), true);
    assert.equal(isToolingMarkdown(".github/agents/demo.agent.md"), true);
    assert.equal(isToolingMarkdown(".github/copilot-instructions.md"), true);
    assert.equal(isToolingMarkdown("docs/development/rules.md"), false);
  });
});

describe("OKF index generation and repository checks", () => {
  it("generates a deterministic index, preserves manual text, and ignores untracked/tooling Markdown", async () => {
    const directory = await createGitRepository();
    try {
      await writeRepositoryFixture(directory);

      const updateResult = await updateIndex(directory);
      assert.equal(updateResult.changed, true);

      const index = await readFile(join(directory, "index.md"), "utf8");
      assert.match(index, /Manual introduction\./);
      assert.match(index, /Manual conclusion\./);
      assert.match(index, /Test document/);
      assert.match(index, /documentation/);
      assert.doesNotMatch(index, /tool-specific document/);
      assert.doesNotMatch(index, /untracked\.md/);

      const checkResult = await checkRepository(directory);
      assert.equal(checkResult.valid, true);

      const secondUpdate = await updateIndex(directory);
      assert.equal(secondUpdate.changed, false);
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });

  it("detects a stale index without changing files", async () => {
    const directory = await createGitRepository();
    try {
      await writeRepositoryFixture(directory);
      await updateIndex(directory);
      await writeFile(
        join(directory, "README.md"),
        VALID_FRONTMATTER.replace("Test document", "Changed document"),
      );

      const result = await checkRepository(directory);
      assert.equal(result.valid, false);
      assert.ok(
        result.diagnostics.some((item) => item.message.includes("docs:index")),
      );
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });

  it("reports invalid documents without crashing during index comparison", async () => {
    const directory = await createGitRepository();
    try {
      await writeRepositoryFixture(directory);
      await updateIndex(directory);
      await writeFile(join(directory, "bad.md"), "Missing frontmatter\n");
      await trackFiles(directory, ["bad.md"]);

      const result = await checkRepository(directory);
      assert.equal(result.valid, false);
      assert.ok(result.diagnostics.some((item) => item.filePath === "bad.md"));
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });
});
