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
  try {
    return yaml.parse(yamlString);
  } catch (err) {
    errors.push(`YAML 構文エラー: ${err.message}`);
    return null;
  }
}

export function validateMembers(yamlString) {
  const errors = [];
  const parsed = parseYaml(yamlString, errors);
  if (!parsed) return { valid: false, errors, data: [] };

  if (!parsed.members || !Array.isArray(parsed.members)) {
    errors.push("members: 配列が必須です");
    return { valid: false, errors, data: [] };
  }

  const seenIds = new Set();
  const members = [];

  for (let i = 0; i < parsed.members.length; i++) {
    const m = parsed.members[i];
    const prefix = `members[${i}]`;

    if (!m || typeof m !== "object") {
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

    const maxCapacity = m.max_capacity ?? 1.0;
    if (
      typeof maxCapacity !== "number" ||
      maxCapacity <= 0 ||
      maxCapacity > 1.0
    ) {
      errors.push(
        `${prefix}.max_capacity: 0.0 超 1.0 以下の数値である必要があります (指定値: ${maxCapacity})`,
      );
    }

    const skills = m.skills ?? [];
    if (!Array.isArray(skills) || skills.some((s) => typeof s !== "string")) {
      errors.push(`${prefix}.skills: 文字列の配列である必要があります`);
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
  if (!parsed) return { valid: false, errors, data: [] };

  if (!parsed.tasks || !Array.isArray(parsed.tasks)) {
    errors.push("tasks: 配列が必須です");
    return { valid: false, errors, data: [] };
  }

  const seenIds = new Set();
  const tasks = [];

  for (let i = 0; i < parsed.tasks.length; i++) {
    const t = parsed.tasks[i];
    const prefix = `tasks[${i}]`;

    if (!t || typeof t !== "object") {
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

    if (typeof t.estimate_hours !== "number" || t.estimate_hours <= 0) {
      errors.push(
        `${prefix}.estimate_hours: 0 より大きい正の数値である必要があります`,
      );
    }

    const requiredSkills = t.required_skills ?? [];
    if (
      !Array.isArray(requiredSkills) ||
      requiredSkills.some((s) => typeof s !== "string")
    ) {
      errors.push(
        `${prefix}.required_skills: 文字列の配列である必要があります`,
      );
    }

    const dependsOn = t.depends_on ?? [];
    if (
      !Array.isArray(dependsOn) ||
      dependsOn.some((d) => typeof d !== "string")
    ) {
      errors.push(`${prefix}.depends_on: 文字列の配列である必要があります`);
    }

    if (t.deadline !== undefined && t.deadline !== null) {
      if (!isValidDate(t.deadline)) {
        errors.push(
          `${prefix}.deadline: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: ${t.deadline})`,
        );
      }
    }

    tasks.push({
      id: t.id,
      title: t.title,
      estimate_hours: t.estimate_hours,
      required_skills: requiredSkills,
      depends_on: dependsOn,
      deadline: t.deadline ?? null,
    });
  }

  return { valid: errors.length === 0, errors, data: tasks };
}

export function validateCalendar(yamlString) {
  const errors = [];
  const parsed = parseYaml(yamlString, errors);
  if (!parsed) return { valid: false, errors, data: null };

  const cal = parsed.calendar;
  if (!cal || typeof cal !== "object") {
    errors.push("calendar: オブジェクトが必須です");
    return { valid: false, errors, data: null };
  }

  const workdays = cal.workdays ?? ["mon", "tue", "wed", "thu", "fri"];
  if (
    !Array.isArray(workdays) ||
    workdays.some((w) => !VALID_WORKDAYS.has(w))
  ) {
    errors.push(
      "calendar.workdays: 有効な曜日 (mon, tue, wed, thu, fri, sat, sun) の配列である必要があります",
    );
  }

  const rawHolidays = cal.holidays ?? [];
  const holidays = [];
  if (!Array.isArray(rawHolidays)) {
    errors.push("calendar.holidays: 配列である必要があります");
  } else {
    for (let i = 0; i < rawHolidays.length; i++) {
      const h = rawHolidays[i];
      const prefix = `calendar.holidays[${i}]`;
      if (!h || typeof h !== "object") {
        errors.push(`${prefix}: オブジェクトである必要があります`);
        continue;
      }
      if (!h.date || !isValidDate(h.date)) {
        errors.push(
          `${prefix}.date: 有効な YYYY-MM-DD 形式の日付である必要があります (指定値: ${h?.date})`,
        );
      }
      holidays.push({
        date: h.date,
        name: typeof h.name === "string" ? h.name : "",
      });
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
  let members = null;
  let tasks = null;
  let calendar = null;

  try {
    const content = await readFile(join(dirPath, "members.yaml"), "utf-8");
    const res = validateMembers(content);
    if (!res.valid) errors.push(...res.errors);
    members = res.data;
  } catch (err) {
    errors.push(`members.yaml 読み込み失敗: ${err.message}`);
  }

  try {
    const content = await readFile(join(dirPath, "tasks.yaml"), "utf-8");
    const res = validateTasks(content);
    if (!res.valid) errors.push(...res.errors);
    tasks = res.data;
  } catch (err) {
    errors.push(`tasks.yaml 読み込み失敗: ${err.message}`);
  }

  try {
    const content = await readFile(join(dirPath, "calendar.yaml"), "utf-8");
    const res = validateCalendar(content);
    if (!res.valid) errors.push(...res.errors);
    calendar = res.data;
  } catch (err) {
    errors.push(`calendar.yaml 読み込み失敗: ${err.message}`);
  }

  return {
    valid: errors.length === 0,
    errors,
    members,
    tasks,
    calendar,
  };
}
