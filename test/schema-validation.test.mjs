import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  validateMembers,
  validateTasks,
  validateCalendar,
  validateProjectData,
} from "../src/validator.mjs";

const BASIC_DIR = join(import.meta.dirname, "../examples/basic");

describe("YAML Schema Validation (001-yaml-schema)", () => {
  describe("Scenario 1: 正常系原本データの読み込みと検証 (AC-1, AC-2, AC-3)", () => {
    it("members.yaml が正しく検証され、メンバ情報が取得できること", async () => {
      const content = await readFile(join(BASIC_DIR, "members.yaml"), "utf-8");
      const result = validateMembers(content);
      assert.equal(result.valid, true);
      assert.equal(result.errors.length, 0);
      assert.equal(result.data.length, 2);

      const [alice, bob] = result.data;
      assert.equal(alice.id, "alice");
      assert.equal(alice.name, "Alice");
      assert.equal(alice.max_capacity, 1.0);
      assert.deepEqual(alice.skills, ["frontend", "backend"]);

      assert.equal(bob.id, "bob");
      assert.equal(bob.max_capacity, 0.8);
      assert.deepEqual(bob.skills, ["backend", "devops"]);
    });

    it("tasks.yaml が正しく検証され、タスク情報が取得できること", async () => {
      const content = await readFile(join(BASIC_DIR, "tasks.yaml"), "utf-8");
      const result = validateTasks(content);
      assert.equal(result.valid, true);
      assert.equal(result.errors.length, 0);
      assert.equal(result.data.length, 2);

      const [taskApi, taskUi] = result.data;
      assert.equal(taskApi.id, "task-api");
      assert.equal(taskApi.estimate_hours, 16);
      assert.deepEqual(taskApi.required_skills, ["backend"]);
      assert.deepEqual(taskApi.depends_on, []);
      assert.equal(taskApi.deadline, "2026-09-20");

      assert.equal(taskUi.id, "task-ui");
      assert.equal(taskUi.estimate_hours, 24);
      assert.deepEqual(taskUi.depends_on, ["task-api"]);
    });

    it("calendar.yaml が正しく検証され、カレンダー情報が取得できること", async () => {
      const content = await readFile(join(BASIC_DIR, "calendar.yaml"), "utf-8");
      const result = validateCalendar(content);
      assert.equal(result.valid, true);
      assert.equal(result.errors.length, 0);
      assert.deepEqual(result.data.workdays, [
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
      ]);
      assert.equal(result.data.holidays.length, 2);
      assert.equal(result.data.holidays[0].date, "2026-09-15");
      assert.equal(result.data.holidays[0].name, "敬老の日");
    });

    it("validateProjectData でディレクトリ内の全ファイルを一括検証できること", async () => {
      const result = await validateProjectData(BASIC_DIR);
      assert.equal(result.valid, true);
      assert.equal(result.errors.length, 0);
      assert.ok(result.members);
      assert.ok(result.tasks);
      assert.ok(result.calendar);
    });
  });

  describe("Scenario 2: 必須フィールド欠落時の検知", () => {
    it("メンバの id が欠落している場合にエラーを検知すること", () => {
      const yaml = `
members:
  - name: "No ID Member"
`;
      const result = validateMembers(yaml);
      assert.equal(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes("id")));
    });

    it("タスクの estimate_hours が欠落している場合にエラーを検知すること", () => {
      const yaml = `
tasks:
  - id: "t1"
    title: "Task without estimate"
`;
      const result = validateTasks(yaml);
      assert.equal(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes("estimate_hours")));
    });

    it("カレンダーの holidays で date が欠落している場合にエラーを検知すること", () => {
      const yaml = `
calendar:
  holidays:
    - name: "Holiday without date"
`;
      const result = validateCalendar(yaml);
      assert.equal(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes("date")));
    });
  });

  describe("Scenario 3: 不正な型・制約違反の検知", () => {
    it("max_capacity が範囲外（1.0 超または 0 以下）の場合にエラーを検知すること", () => {
      const yamlOver = `
members:
  - id: "m1"
    name: "Over"
    max_capacity: 1.5
`;
      assert.equal(validateMembers(yamlOver).valid, false);

      const yamlZero = `
members:
  - id: "m2"
    name: "Zero"
    max_capacity: 0.0
`;
      assert.equal(validateMembers(yamlZero).valid, false);
    });

    it("タスクの estimate_hours が 0 以下の数値または文字列の場合にエラーを検知すること", () => {
      const yamlZero = `
tasks:
  - id: "t1"
    title: "Zero hours"
    estimate_hours: 0
`;
      assert.equal(validateTasks(yamlZero).valid, false);

      const yamlString = `
tasks:
  - id: "t2"
    title: "String hours"
    estimate_hours: "five"
`;
      assert.equal(validateTasks(yamlString).valid, false);
    });

    it("タスクの deadline が不正な日付形式の場合にエラーを検知すること", () => {
      const yamlInvalidDate = `
tasks:
  - id: "t1"
    title: "Invalid date"
    estimate_hours: 8
    deadline: "2026-02-30"
`;
      const result = validateTasks(yamlInvalidDate);
      assert.equal(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes("deadline")));
    });

    it("calendar の workdays に無効な曜日が含まれている場合にエラーを検知すること", () => {
      const yaml = `
calendar:
  workdays: [mon, tue, funday]
`;
      const result = validateCalendar(yaml);
      assert.equal(result.valid, false);
      assert.ok(result.errors.some((e) => e.includes("workdays")));
    });

    it("id が重複している場合にエラーを検知すること", () => {
      const yamlDuplicate = `
members:
  - id: "m1"
    name: "Member 1"
  - id: "m1"
    name: "Member 1 Duplicate"
`;
      const result = validateMembers(yamlDuplicate);
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (e) => e.includes("重複") || e.includes("duplicate"),
        ),
      );
    });
  });
});
