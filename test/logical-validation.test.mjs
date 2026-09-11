import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { validateLogicalIntegrity } from "../src/validator.mjs";

describe("Logical Integrity Validation (001-yaml-schema Scenario 5)", () => {
  const validMembers = [
    {
      id: "alice",
      name: "Alice",
      max_capacity: 1.0,
      skills: ["frontend", "backend"],
    },
    {
      id: "bob",
      name: "Bob",
      max_capacity: 0.8,
      skills: ["backend", "devops"],
    },
  ];

  const validTasks = [
    {
      id: "task-api",
      title: "API 実装",
      estimate_hours: 16,
      required_skills: ["backend"],
      depends_on: [],
      deadline: "2026-09-20",
    },
    {
      id: "task-ui",
      title: "UI 実装",
      estimate_hours: 24,
      required_skills: ["frontend"],
      depends_on: ["task-api"],
      deadline: "2026-09-25",
    },
  ];

  const validCalendar = {
    workdays: ["mon", "tue", "wed", "thu", "fri"],
    holidays: [],
  };

  it("正常な原本データ（DAG、有効参照）で検証が成功すること", () => {
    const result = validateLogicalIntegrity(
      validMembers,
      validTasks,
      validCalendar,
    );
    assert.equal(result.valid, true);
    assert.deepEqual(result.errors, []);
  });

  describe("AC-1: タスク循環依存の検知", () => {
    it("2要素の循環依存（A -> B -> A）を検知し循環パスとヒントを出力すること", () => {
      const tasks = [
        {
          id: "task-a",
          title: "Task A",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-b"],
          deadline: null,
        },
        {
          id: "task-b",
          title: "Task B",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-a"],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) =>
            (err.includes("task-a -> task-b -> task-a") ||
              err.includes("task-b -> task-a -> task-b")) &&
            err.includes("循環"),
        ),
        `期待する循環エラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });

    it("3要素以上の循環依存（A -> B -> C -> A）を検知し循環パスとヒントを出力すること", () => {
      const tasks = [
        {
          id: "task-a",
          title: "Task A",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-b"],
          deadline: null,
        },
        {
          id: "task-b",
          title: "Task B",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-c"],
          deadline: null,
        },
        {
          id: "task-c",
          title: "Task C",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-a"],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) =>
            err.includes("循環") &&
            (err.includes("task-a -> task-b -> task-c -> task-a") ||
              err.includes("task-b -> task-c -> task-a -> task-b") ||
              err.includes("task-c -> task-a -> task-b -> task-c")),
        ),
        `期待する循環エラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });

    it("自己参照（A -> A）を検知しヒントを出力すること", () => {
      const tasks = [
        {
          id: "task-self",
          title: "Task Self",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-self"],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) => err.includes("task-self") && err.includes("循環"),
        ),
        `期待する自己参照循環エラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });
  });

  describe("AC-2: 未定義タスク参照の検知", () => {
    it("depends_on に存在しないタスク ID が指定されている場合に未定義参照エラーを出力すること", () => {
      const tasks = [
        {
          id: "task-ui",
          title: "Task UI",
          estimate_hours: 8,
          required_skills: [],
          depends_on: ["task-nonexistent"],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) =>
            err.includes("task-nonexistent") &&
            err.includes("task-ui") &&
            err.includes("未定義"),
        ),
        `期待する未定義タスクエラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });
  });

  describe("AC-3: 未定義スキル参照の検知", () => {
    it("タスクの required_skills を保有するメンバが 1 人もいない場合にエラーを出力すること", () => {
      const tasks = [
        {
          id: "task-quantum",
          title: "量子計算",
          estimate_hours: 8,
          required_skills: ["quantum-computing"],
          depends_on: [],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) =>
            err.includes("quantum-computing") &&
            err.includes("task-quantum") &&
            (err.includes("保有") || err.includes("メンバ")),
        ),
        `期待する未定義スキルエラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });

    it("個別スキルはチーム内に存在するが、単一メンバで兼任できない複数スキル要求を検知すること", () => {
      // validMembers: alice [frontend, backend], bob [backend, devops]
      const tasks = [
        {
          id: "task-split-skills",
          title: "兼任不能スキルタスク",
          estimate_hours: 8,
          required_skills: ["frontend", "devops"],
          depends_on: [],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) =>
            err.includes("task-split-skills") &&
            err.includes("frontend") &&
            err.includes("devops") &&
            (err.includes("保有") || err.includes("メンバ")),
        ),
        `期待する兼任不能スキルエラーが含まれていません: ${JSON.stringify(result.errors)}`,
      );
    });
  });

  describe("AC-4: 診断メッセージと解決ヒント", () => {
    it("エラーメッセージに対象タスク ID と解決のヒントが含まれていること", () => {
      const tasks = [
        {
          id: "task-x",
          title: "Task X",
          estimate_hours: 8,
          required_skills: ["unknown-skill"],
          depends_on: ["task-y"],
          deadline: null,
        },
      ];

      const result = validateLogicalIntegrity(
        validMembers,
        tasks,
        validCalendar,
      );
      assert.equal(result.valid, false);
      assert.ok(
        result.errors.some(
          (err) => err.includes("task-y") && err.includes("解決"),
        ),
        "未定義タスク参照エラーにヒントが含まれること",
      );
      assert.ok(
        result.errors.some(
          (err) => err.includes("unknown-skill") && err.includes("解決"),
        ),
        "未定義スキル参照エラーにヒントが含まれること",
      );
    });
  });
});
