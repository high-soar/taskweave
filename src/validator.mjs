import { readFile } from "node:fs/promises";
import { join } from "node:path";
import yaml from "yaml";

const VALID_WORKDAYS = new Set([
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
]);

function isValidDate(str) {
  if (typeof str !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(str)) return false;
  const [y, m, d] = str.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return (
    date.getUTCFullYear() === y &&
    date.getUTCMonth() === m - 1 &&
    date.getUTCDate() === d
  );
}

function parseYaml(yamlString, errors) {
  if (typeof yamlString !== "string" || yamlString.trim() === "") {
    errors.push("YAML ドキュメントが空です");
    return null;
  }
  try {
    const parsed = yaml.parse(yamlString);
    if (parsed === null || parsed === undefined) {
      errors.push("YAML にデータが含まれていません");
      return null;
    }
    return parsed;
  } catch (err) {
    errors.push(`YAML 構文エラー: ${err.message}`);
    return null;
  }
}

export function validateMembers(yamlString) {
  const errors = [];
  const parsed = parseYaml(yamlString, errors);
  if (parsed === null) return { valid: false, errors, data: [] };

  if (!parsed.members || !Array.isArray(parsed.members)) {
    errors.push("members: 配列が必須です");
    return { valid: false, errors, data: [] };
  }

  const seenIds = new Set();
  const members = [];

  for (let i = 0; i < parsed.members.length; i++) {
    const m = parsed.members[i];
    const prefix = `members[${i}]`;

    if (!m || typeof m !== "object" || Array.isArray(m)) {
      errors.push(`${prefix}: オブジェクトである必要があります`);
      continue;
    }

    if (!m.id || typeof m.id !== "string") {
      errors.push(`${prefix}.id: 必須の文字列です`);
    } else if (seenIds.has(m.id)) {
      errors.push(`${prefix}.id: "${m.id}" は重複しています`);
    } else {
      seenIds.add(m.id);
    }

    if (!m.name || typeof m.name !== "string") {
      errors.push(`${prefix}.name: 必須の文字列です`);
    }

    let maxCapacity = 1.0;
    if (m.max_capacity !== undefined) {
      if (
        typeof m.max_capacity !== "number" ||
        !Number.isFinite(m.max_capacity) ||
        m.max_capacity <= 0 ||
        m.max_capacity > 1.0
      ) {
        errors.push(
          `${prefix}.max_capacity: 0.0 超 1.0 以下の有限な数値である必要があります (指定値: ${m.max_capacity})`,
        );
      } else {
        maxCapacity = m.max_capacity;
      }
    }

    let skills = [];
    if (m.skills !== undefined) {
      if (
        !Array.isArray(m.skills) ||
        skills.some((s) => typeof s !== "string")
      ) {
        errors.push(`${prefix}.skills: 文字列の配列である必要があります`);
      } else if (m.skills.some((s) => typeof s !== "string")) {
        errors.push(`${prefix}.skills: 文字列の配列である必要があります`);
      } else {
        skills = m.skills;
      }
    }

    members.push({
      id: m.id,
      name: m.name,
      max_capacity: maxCapacity,
      skills,
    });
  }

  return { valid: errors.length === 0, errors, data: members };
}

export function validateTasks(yamlString) {
  const errors = [];
  const parsed = parseYaml(yamlString, errors);
  if (parsed === null) return { valid: false, errors, data: [] };

  if (!parsed.tasks || !Array.isArray(parsed.tasks)) {
    errors.push("tasks: 配列が必須です");
    return { valid: false, errors, data: [] };
  }

  const seenIds = new Set();
  const tasks = [];

  for (let i = 0; i < parsed.tasks.length; i++) {
    const t = parsed.tasks[i];
    const prefix = `tasks[${i}]`;

    if (!t || typeof t !== "object" || Array.isArray(t)) {
      errors.push(`${prefix}: オブジェクトである必要があります`);
      continue;
    }

    if (!t.id || typeof t.id !== "string") {
      errors.push(`${prefix}.id: 必須の文字列です`);
    } else if (seenIds.has(t.id)) {
      errors.push(`${prefix}.id: "${t.id}" は重複しています`);
    } else {
      seenIds.add(t.id);
    }

    if (!t.title || typeof t.title !== "string") {
      errors.push(`${prefix}.title: 必須の文字列です`);
    }

    const isStep01 =
      typeof t.estimate_hours === "number" &&
      Number.isFinite(t.estimate_hours) &&
      t.estimate_hours >= 0.1 &&
      Math.abs(t.estimate_hours - Math.round(t.estimate_hours * 10) / 10) <
        1e-6;

    if (!isStep01) {
      errors.push(
        `${prefix}.estimate_hours: 0.1 以上の 0.1 時間刻み（小数点以下1桁まで）の正の数値である必要があります`,
      );
    }

    let requiredSkills = [];
    if (t.required_skills !== undefined) {
      if (
        !Array.isArray(t.required_skills) ||
        t.required_skills.some((s) => typeof s !== "string")
      ) {
        errors.push(
          `${prefix}.required_skills: 文字列の配列である必要があります`,
        );
      } else {
        requiredSkills = t.required_skills;
      }
    }

    let dependsOn = [];
    if (t.depends_on !== undefined) {
      if (
        !Array.isArray(t.depends_on) ||
        t.depends_on.some((d) => typeof d !== "string")
      ) {
        errors.push(`${prefix}.depends_on: 文字列の配列である必要があります`);
      } else {
        dependsOn = t.depends_on;
      }
    }

    let deadline = null;
    if (t.deadline !== undefined && t.deadline !== null) {
      if (!isValidDate(t.deadline)) {
        errors.push(
          `${prefix}.deadline: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: ${t.deadline})`,
        );
      } else {
        deadline = t.deadline;
      }
    }

    tasks.push({
      id: t.id,
      title: t.title,
      estimate_hours: t.estimate_hours,
      required_skills: requiredSkills,
      depends_on: dependsOn,
      deadline,
    });
  }

  return { valid: errors.length === 0, errors, data: tasks };
}

export function validateCalendar(yamlString) {
  const errors = [];
  const parsed = parseYaml(yamlString, errors);
  if (parsed === null) return { valid: false, errors, data: null };

  const cal = parsed.calendar;
  if (!cal || typeof cal !== "object" || Array.isArray(cal)) {
    errors.push("calendar: オブジェクトが必須です");
    return { valid: false, errors, data: null };
  }

  let workdays = ["mon", "tue", "wed", "thu", "fri"];
  if (cal.workdays !== undefined) {
    if (
      !Array.isArray(cal.workdays) ||
      cal.workdays.some((w) => !VALID_WORKDAYS.has(w))
    ) {
      errors.push(
        "calendar.workdays: 有効な曜日 (mon, tue, wed, thu, fri, sat, sun) の配列である必要があります",
      );
    } else if (cal.workdays.length === 0) {
      errors.push(
        "calendar.workdays: 少なくとも1つの有効な稼働曜日を指定する必要があります",
      );
    } else {
      const seenWorkdays = new Set();
      for (const w of cal.workdays) {
        if (seenWorkdays.has(w)) {
          errors.push(`calendar.workdays: "${w}" は重複しています`);
        } else {
          seenWorkdays.add(w);
        }
      }
      workdays = cal.workdays;
    }
  }

  let holidays = [];
  const seenDates = new Set();
  if (cal.holidays !== undefined) {
    if (!Array.isArray(cal.holidays)) {
      errors.push("calendar.holidays: 配列である必要があります");
    } else {
      for (let i = 0; i < cal.holidays.length; i++) {
        const h = cal.holidays[i];
        const prefix = `calendar.holidays[${i}]`;
        if (!h || typeof h !== "object" || Array.isArray(h)) {
          errors.push(`${prefix}: オブジェクトである必要があります`);
          continue;
        }
        if (!h.date || !isValidDate(h.date)) {
          errors.push(
            `${prefix}.date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: ${h?.date})`,
          );
        } else if (seenDates.has(h.date)) {
          errors.push(`${prefix}.date: "${h.date}" は重複しています`);
        } else {
          seenDates.add(h.date);
        }
        let name = "";
        if (h.name !== undefined) {
          if (typeof h.name !== "string") {
            errors.push(`${prefix}.name: 文字列である必要があります`);
          } else {
            name = h.name;
          }
        }
        holidays.push({
          date: h.date,
          name,
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    data: { workdays, holidays },
  };
}

export async function validateProjectData(dirPath) {
  const errors = [];
  let allValid = true;
  let members = null;
  let tasks = null;
  let calendar = null;

  try {
    const content = await readFile(join(dirPath, "members.yaml"), "utf-8");
    const res = validateMembers(content);
    if (!res.valid) {
      allValid = false;
      errors.push(...res.errors);
    }
    members = res.data;
  } catch (err) {
    allValid = false;
    errors.push(`members.yaml 読み込み失敗: ${err.message}`);
  }

  try {
    const content = await readFile(join(dirPath, "tasks.yaml"), "utf-8");
    const res = validateTasks(content);
    if (!res.valid) {
      allValid = false;
      errors.push(...res.errors);
    }
    tasks = res.data;
  } catch (err) {
    allValid = false;
    errors.push(`tasks.yaml 読み込み失敗: ${err.message}`);
  }

  try {
    const content = await readFile(join(dirPath, "calendar.yaml"), "utf-8");
    const res = validateCalendar(content);
    if (!res.valid) {
      allValid = false;
      errors.push(...res.errors);
    }
    calendar = res.data;
  } catch (err) {
    allValid = false;
    errors.push(`calendar.yaml 読み込み失敗: ${err.message}`);
  }

  if (allValid && members && tasks && calendar) {
    const logicalRes = validateLogicalIntegrity(members, tasks);
    if (!logicalRes.valid) {
      allValid = false;
      errors.push(...logicalRes.errors);
    }
  }

  return {
    valid: allValid && errors.length === 0,
    errors,
    members,
    tasks,
    calendar,
  };
}

export function validateLogicalIntegrity(members, tasks) {
  const errors = [];
  if (!Array.isArray(tasks)) return { valid: true, errors: [] };

  const taskMap = new Map();
  for (let i = 0; i < tasks.length; i++) {
    const t = tasks[i];
    if (t && typeof t.id === "string") {
      taskMap.set(t.id, { index: i, task: t });
    }
  }

  // 1. 未定義タスク参照チェック (Undefined Task Reference)
  for (let i = 0; i < tasks.length; i++) {
    const t = tasks[i];
    if (!t || !Array.isArray(t.depends_on)) continue;
    for (let d = 0; d < t.depends_on.length; d++) {
      const depId = t.depends_on[d];
      if (!taskMap.has(depId)) {
        errors.push(
          `tasks[${i}].depends_on[${d}]: 未定義のタスク "${depId}" を参照しています (参照元: "${t.id}")。解決のヒント: 存在するタスク ID を指定するか、tasks.yaml にタスクを追加してください`,
        );
      }
    }
  }

  // 2. 循環依存検知 (DFS Cycle Detection)
  const visited = new Map();
  const reportedCycles = new Set();

  function dfs(taskId, path) {
    visited.set(taskId, 1);
    path.push(taskId);

    const entry = taskMap.get(taskId);
    const dependsOn = entry?.task?.depends_on;
    if (Array.isArray(dependsOn)) {
      for (const nextId of dependsOn) {
        if (!taskMap.has(nextId)) continue;

        const state = visited.get(nextId);
        if (state === 1) {
          const cycleStart = path.indexOf(nextId);
          const cycleNodes = path.slice(cycleStart);
          const cyclePath = [...cycleNodes, nextId].join(" -> ");

          const cycleKey = [...cycleNodes].sort().join(",");
          if (!reportedCycles.has(cycleKey)) {
            reportedCycles.add(cycleKey);
            const taskIndex = entry?.index ?? 0;
            errors.push(
              `tasks[${taskIndex}].depends_on: タスク依存関係に循環参照が検出されました: ${cyclePath}。解決のヒント: 先行・後続の依存関係を見直して循環を解消してください`,
            );
          }
        } else if (!state) {
          dfs(nextId, path);
        }
      }
    }

    path.pop();
    visited.set(taskId, 2);
  }

  for (const taskId of taskMap.keys()) {
    if (!visited.has(taskId)) {
      dfs(taskId, []);
    }
  }

  // 3. 未定義スキル参照チェック (Undefined Skill Reference)
  if (Array.isArray(members)) {
    const teamSkills = new Set();
    for (const m of members) {
      if (Array.isArray(m?.skills)) {
        for (const s of m.skills) {
          if (typeof s === "string") teamSkills.add(s);
        }
      }
    }

    for (let i = 0; i < tasks.length; i++) {
      const t = tasks[i];
      if (!t || !Array.isArray(t.required_skills)) continue;
      for (let s = 0; s < t.required_skills.length; s++) {
        const skill = t.required_skills[s];
        if (typeof skill === "string" && !teamSkills.has(skill)) {
          errors.push(
            `tasks[${i}].required_skills[${s}]: タスク "${t.id}" の必須スキル "${skill}" を保有するメンバが存在しません。解決のヒント: members.yaml の skills にスキルを追加するか、タスクの必須スキルを見直してください`,
          );
        }
      }
    }
  }

  return { valid: errors.length === 0, errors };
}
