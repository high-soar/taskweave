import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import yaml from "yaml";
import {
  validateCalendar,
  validateMembers,
  validateTasks,
} from "../src/validator.mjs";

const FILES = [
  ["members.yaml", validateMembers],
  ["tasks.yaml", validateTasks],
  ["calendar.yaml", validateCalendar],
];

function getErrorPath(message) {
  const match = message.match(
    /^((?:members|tasks|calendar)(?:\[\d+\])?(?:\.[\w-]+(?:\[\d+\])?)*)\s*:/,
  );
  if (!match) return [];

  return match[1].replaceAll("[", ".").replaceAll("]", "").split(".");
}

function getNodeLine(document, path, lineCounter) {
  for (let end = path.length; end > 0; end--) {
    const node = document.getIn(path.slice(0, end), true);
    if (node?.range) return lineCounter.linePos(node.range[0]).line;
  }
  return null;
}

function getErrorLine(source, message) {
  const lineCounter = new yaml.LineCounter();
  let document;

  try {
    document = yaml.parseDocument(source, { lineCounter });
  } catch {
    return 1;
  }

  const pathLine = getNodeLine(document, getErrorPath(message), lineCounter);
  if (pathLine !== null) return pathLine;

  const position = document.errors[0]?.pos?.[0];
  return typeof position === "number" ? lineCounter.linePos(position).line : 1;
}

async function validateDirectory(directory) {
  let hasErrors = false;

  for (const [fileName, validate] of FILES) {
    const filePath = join(directory, fileName);
    let source;

    try {
      source = await readFile(filePath, "utf-8");
    } catch (error) {
      hasErrors = true;
      console.error(`${fileName}:1: 読み込み失敗: ${error.message}`);
      continue;
    }

    const result = validate(source);
    if (!result.valid) hasErrors = true;
    for (const error of result.errors) {
      hasErrors = true;
      const line = getErrorLine(source, error);
      console.error(`${fileName}:${line}: ${error}`);
    }
  }

  return hasErrors;
}

const directory = resolve(process.cwd(), process.argv[2] ?? "data");
const hasErrors = await validateDirectory(directory);

if (hasErrors) {
  process.exitCode = 1;
} else {
  console.log(`YAML 原本データの検証に成功しました: ${directory}`);
}
