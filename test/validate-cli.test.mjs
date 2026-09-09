import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";

const execFileAsync = promisify(execFile);
const ROOT_DIR = join(import.meta.dirname, "..");
const BASIC_DIR = join(ROOT_DIR, "examples/basic");
const CLI_PATH = join(ROOT_DIR, "scripts/validate.mjs");

describe("validate CLI", () => {
  it("正常な原本データを成功終了し、成功メッセージを出力すること", async () => {
    const result = await execFileAsync(process.execPath, [CLI_PATH, BASIC_DIR]);

    assert.equal(result.stderr, "");
    assert.match(result.stdout, /検証に成功/);
  });

  it("検証エラーにファイル名、行番号、キー名を含めること", async () => {
    const testDir = await mkdtemp(join(ROOT_DIR, ".tmp-validation-"));

    try {
      await Promise.all(
        ["members.yaml", "calendar.yaml"].map(async (fileName) => {
          const content = await readFile(join(BASIC_DIR, fileName), "utf-8");
          await writeFile(join(testDir, fileName), content);
        }),
      );
      await writeFile(
        join(testDir, "tasks.yaml"),
        `tasks:\n  - id: task-missing-estimate\n    title: "Missing estimate"\n`,
      );

      await assert.rejects(
        execFileAsync(process.execPath, [CLI_PATH, testDir]),
        (error) => {
          assert.equal(error.code, 1);
          assert.match(error.stderr, /tasks\.yaml:\d+:.*estimate_hours/);
          return true;
        },
      );
    } finally {
      await rm(testDir, { recursive: true, force: true });
    }
  });

  it("不正な型や負の工数をファイル名と行番号付きで報告すること", async () => {
    const testDir = await mkdtemp(join(ROOT_DIR, ".tmp-validation-"));

    try {
      await Promise.all(
        ["members.yaml", "calendar.yaml"].map(async (fileName) => {
          const content = await readFile(join(BASIC_DIR, fileName), "utf-8");
          await writeFile(join(testDir, fileName), content);
        }),
      );
      await writeFile(
        join(testDir, "tasks.yaml"),
        `tasks:\n  - id: task-string-estimate\n    title: "String estimate"\n    estimate_hours: eight\n  - id: task-negative-estimate\n    title: "Negative estimate"\n    estimate_hours: -1\n`,
      );

      await assert.rejects(
        execFileAsync(process.execPath, [CLI_PATH, testDir]),
        (error) => {
          assert.equal(error.code, 1);
          assert.match(error.stderr, /tasks\.yaml:4:.*estimate_hours.*数値/);
          return true;
        },
      );
    } finally {
      await rm(testDir, { recursive: true, force: true });
    }
  });

  it("ルート要素がスカラーの YAML を成功扱いしないこと", async () => {
    const testDir = await mkdtemp(join(ROOT_DIR, ".tmp-validation-"));

    try {
      await writeFile(join(testDir, "members.yaml"), "false\n");
      await Promise.all(
        ["tasks.yaml", "calendar.yaml"].map(async (fileName) => {
          const content = await readFile(join(BASIC_DIR, fileName), "utf-8");
          await writeFile(join(testDir, fileName), content);
        }),
      );

      await assert.rejects(
        execFileAsync(process.execPath, [CLI_PATH, testDir]),
        (error) => {
          assert.equal(error.code, 1);
          assert.match(error.stderr, /members\.yaml:\d+:.*members/);
          return true;
        },
      );
    } finally {
      await rm(testDir, { recursive: true, force: true });
    }
  });

  it("構文エラーをファイル名と行番号付きで報告すること", async () => {
    const testDir = await mkdtemp(join(ROOT_DIR, ".tmp-validation-"));

    try {
      await Promise.all(
        ["members.yaml", "calendar.yaml"].map(async (fileName) => {
          const content = await readFile(join(BASIC_DIR, fileName), "utf-8");
          await writeFile(join(testDir, fileName), content);
        }),
      );
      await writeFile(
        join(testDir, "tasks.yaml"),
        `tasks:\n  - id: task-invalid-yaml\n    title: "Unclosed title\n`,
      );

      await assert.rejects(
        execFileAsync(process.execPath, [CLI_PATH, testDir]),
        (error) => {
          assert.equal(error.code, 1);
          assert.match(error.stderr, /tasks\.yaml:4:.*構文エラー/);
          return true;
        },
      );
    } finally {
      await rm(testDir, { recursive: true, force: true });
    }
  });
});
