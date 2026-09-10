import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import yaml from "yaml";

const execFileAsync = promisify(execFile);

export const ROOT_INDEX_PATH = "index.md";
export const GENERATED_BEGIN = "<!-- BEGIN GENERATED: okf-index -->";
export const GENERATED_END = "<!-- END GENERATED: okf-index -->";

const OKF_TYPE_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const TAG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ACTOR_PATTERN =
  /^(?:human|process):[A-Za-z0-9._-]+$|^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;
const UTC_TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const ALLOWED_STATUSES = new Set([
  "draft",
  "under-review",
  "accepted",
  "implemented",
  "superseded",
  "stable",
  "deprecated",
]);
const TOOLING_PATHS = [
  /^\.github\/skills\//,
  /^\.github\/agents\//,
  /^\.github\/copilot-instructions\.md$/,
];

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function diagnostic(filePath, line, message) {
  return { filePath, line, message };
}

function formatDiagnostic(error) {
  return `${error.filePath}:${error.line}: ${error.message}`;
}

function lineFromOffset(lineCounter, offset, lineOffset = 0) {
  if (typeof offset !== "number") return 1 + lineOffset;
  return lineCounter.linePos(offset).line + lineOffset;
}

export function isToolingMarkdown(filePath) {
  return TOOLING_PATHS.some((pattern) => pattern.test(filePath));
}

export function parseFrontmatter(source) {
  const lines = source.split(/\r?\n/);
  if (lines[0] !== "---") {
    return {
      data: null,
      endLine: null,
      errors: [
        {
          line: 1,
          message: "先頭行に YAML frontmatter の開始区切り `---` が必要です",
        },
      ],
    };
  }

  const endIndex = lines.findIndex(
    (line, index) => index > 0 && line === "---",
  );
  if (endIndex === -1) {
    return {
      data: null,
      endLine: null,
      errors: [
        {
          line: lines.length,
          message: "YAML frontmatter の終了区切り `---` がありません",
        },
      ],
    };
  }

  const frontmatterSource = lines.slice(1, endIndex).join("\n");
  const lineCounter = new yaml.LineCounter();
  const document = yaml.parseDocument(frontmatterSource, { lineCounter });
  if (document.errors.length > 0) {
    return {
      data: null,
      endLine: endIndex + 1,
      errors: document.errors.map((error) => ({
        line: lineFromOffset(lineCounter, error.pos?.[0], 1),
        message: `YAML 構文エラー: ${error.message.replaceAll(/\s+/g, " ").trim()}`,
      })),
    };
  }

  let data;
  try {
    data = document.toJS();
  } catch (error) {
    return {
      data: null,
      endLine: endIndex + 1,
      errors: [{ line: 2, message: `YAML 解析エラー: ${error.message}` }],
    };
  }

  return { data, endLine: endIndex + 1, errors: [] };
}

function isValidUtcTimestamp(value) {
  if (typeof value !== "string" || !UTC_TIMESTAMP_PATTERN.test(value)) {
    return false;
  }

  const date = new Date(value);
  return (
    !Number.isNaN(date.valueOf()) &&
    date.toISOString().replace(".000Z", "Z") === value
  );
}

export function validateOkfDocument(filePath, source) {
  const parsed = parseFrontmatter(source);
  const diagnostics = parsed.errors.map((error) =>
    diagnostic(filePath, error.line, error.message),
  );

  if (diagnostics.length > 0) {
    return { valid: false, data: null, endLine: parsed.endLine, diagnostics };
  }

  if (!isRecord(parsed.data)) {
    diagnostics.push(
      diagnostic(
        filePath,
        2,
        "frontmatter は YAML のマッピングである必要があります",
      ),
    );
    return { valid: false, data: null, endLine: parsed.endLine, diagnostics };
  }

  const { data } = parsed;
  const frontmatterLine = (field) => {
    const lines = source.split(/\r?\n/);
    const lineIndex = lines.findIndex((line) =>
      new RegExp(`^${field}:`).test(line),
    );
    return lineIndex === -1 ? 2 : lineIndex + 1;
  };

  if (
    typeof data.type !== "string" ||
    !data.type.trim() ||
    !OKF_TYPE_PATTERN.test(data.type)
  ) {
    diagnostics.push(
      diagnostic(
        filePath,
        frontmatterLine("type"),
        "`type` は小文字 kebab-case の空でない文字列である必要があります",
      ),
    );
  }

  for (const field of ["title", "description"]) {
    if (
      typeof data[field] !== "string" ||
      !data[field].trim() ||
      data[field].includes("\n")
    ) {
      diagnostics.push(
        diagnostic(
          filePath,
          frontmatterLine(field),
          `\`${field}\` は空でない 1 行の文字列である必要があります`,
        ),
      );
    }
  }

  if (!Array.isArray(data.tags) || data.tags.length === 0) {
    diagnostics.push(
      diagnostic(
        filePath,
        frontmatterLine("tags"),
        "`tags` は 1 個以上の文字列を持つ配列である必要があります",
      ),
    );
  } else {
    const seenTags = new Set();
    for (const tag of data.tags) {
      if (typeof tag !== "string" || !TAG_PATTERN.test(tag)) {
        diagnostics.push(
          diagnostic(
            filePath,
            frontmatterLine("tags"),
            `タグは小文字 ASCII kebab-case である必要があります: ${String(tag)}`,
          ),
        );
      } else if (seenTags.has(tag)) {
        diagnostics.push(
          diagnostic(
            filePath,
            frontmatterLine("tags"),
            `タグが重複しています: ${tag}`,
          ),
        );
      } else {
        seenTags.add(tag);
      }
    }
  }

  if (!isRecord(data.generated)) {
    diagnostics.push(
      diagnostic(
        filePath,
        frontmatterLine("generated"),
        "`generated` は `by` と `at` を持つマッピングである必要があります",
      ),
    );
  } else {
    if (
      typeof data.generated.by !== "string" ||
      !ACTOR_PATTERN.test(data.generated.by)
    ) {
      diagnostics.push(
        diagnostic(
          filePath,
          frontmatterLine("generated"),
          "`generated.by` は human:<id>、process:<id>、または producer/model 形式である必要があります",
        ),
      );
    }
    if (!isValidUtcTimestamp(data.generated.at)) {
      diagnostics.push(
        diagnostic(
          filePath,
          frontmatterLine("generated"),
          "`generated.at` は有効な ISO 8601 UTC timestamp（YYYY-MM-DDTHH:mm:ssZ）である必要があります",
        ),
      );
    }
  }

  if (data.status !== undefined && !ALLOWED_STATUSES.has(data.status)) {
    diagnostics.push(
      diagnostic(
        filePath,
        frontmatterLine("status"),
        `\`status\` が許可された値ではありません: ${String(data.status)}`,
      ),
    );
  }

  return {
    valid: diagnostics.length === 0,
    data,
    endLine: parsed.endLine,
    diagnostics,
  };
}

async function getTrackedMarkdown(rootDir) {
  const { stdout } = await execFileAsync(
    "git",
    ["ls-files", "-z", "--", "*.md"],
    { cwd: rootDir, encoding: "utf8" },
  );
  return stdout.split("\0").filter(Boolean);
}

async function readOkfEntries(rootDir) {
  const trackedFiles = await getTrackedMarkdown(rootDir);
  const entries = [];
  const diagnostics = [];

  for (const filePath of trackedFiles) {
    if (isToolingMarkdown(filePath)) continue;

    const source = await readFile(join(rootDir, filePath), "utf8");
    const result = validateOkfDocument(filePath, source);
    diagnostics.push(...result.diagnostics);
    entries.push({
      path: filePath,
      source,
      data: result.data,
      valid: result.valid,
    });
  }

  return { entries, diagnostics };
}

function encodedPath(filePath) {
  return filePath.split("/").map(encodeURIComponent).join("/");
}

function markdownText(value) {
  return String(value).replaceAll("[", "\\[").replaceAll("]", "\\]");
}

function sortEntries(entries) {
  return [...entries].sort((left, right) =>
    left.path.localeCompare(right.path),
  );
}

export function renderGeneratedIndex(entries) {
  const documents = sortEntries(
    entries.filter((entry) => entry.path !== ROOT_INDEX_PATH),
  );
  const tagEntries = new Map();

  for (const entry of documents) {
    if (entry.data.type === "index") continue;
    for (const tag of entry.data.tags) {
      const current = tagEntries.get(tag) ?? [];
      current.push(entry);
      tagEntries.set(tag, current);
    }
  }

  const tags = [...tagEntries.keys()].sort((left, right) =>
    left.localeCompare(right),
  );
  const lines = [GENERATED_BEGIN, "", "## Documents", ""];

  for (const entry of documents) {
    lines.push(
      `- [${markdownText(entry.data.title)}](${encodedPath(entry.path)}) - ${markdownText(entry.data.description)}`,
    );
  }

  lines.push("", "## Tags", "");
  for (const tag of tags) {
    lines.push(`- [${tag}](#tag-${tag})`);
  }

  for (const tag of tags) {
    lines.push("", `### Tag: ${tag}`, "");
    for (const entry of sortEntries(tagEntries.get(tag))) {
      lines.push(
        `- [${markdownText(entry.data.title)}](${encodedPath(entry.path)}) - ${markdownText(entry.data.description)}`,
      );
    }
  }

  lines.push("", GENERATED_END);
  return lines.join("\n");
}

function extractGeneratedSection(source) {
  const begin = source.indexOf(GENERATED_BEGIN);
  const end = source.indexOf(GENERATED_END);
  if (begin === -1 || end === -1 || end < begin) return null;
  return source.slice(begin, end + GENERATED_END.length);
}

function replaceGeneratedSection(source, generatedSection) {
  const begin = source.indexOf(GENERATED_BEGIN);
  const end = source.indexOf(GENERATED_END);
  if (begin === -1 || end === -1 || end < begin) {
    throw new Error(
      `root ${ROOT_INDEX_PATH} に生成領域のマーカーがありません: ${GENERATED_BEGIN} / ${GENERATED_END}`,
    );
  }

  return `${source.slice(0, begin)}${generatedSection}${source.slice(end + GENERATED_END.length)}`;
}

const DEFAULT_INDEX = `---
type: index
title: Taskweave 文書インデックス
description: Taskweave の Git 管理文書とタグを一覧する入口
tags: [documentation, index]
generated: { by: process:okf-docs, at: 2026-09-10T11:11:30Z }
---

# Taskweave 文書インデックス

Taskweave の通常プロジェクト文書を一覧します。タグは各文書の frontmatter から自動集約されます。

${GENERATED_BEGIN}
${GENERATED_END}
`;

function throwDiagnostics(diagnostics) {
  const error = new Error("OKF 文書の検査に失敗しました");
  error.diagnostics = diagnostics;
  throw error;
}

export async function updateIndex(rootDir) {
  const { entries, diagnostics } = await readOkfEntries(rootDir);
  if (diagnostics.length > 0) throwDiagnostics(diagnostics);

  const indexFile = join(rootDir, ROOT_INDEX_PATH);
  const source = existsSync(indexFile)
    ? await readFile(indexFile, "utf8")
    : DEFAULT_INDEX;
  const updated = replaceGeneratedSection(
    source,
    renderGeneratedIndex(entries),
  );

  if (updated !== source) {
    await writeFile(indexFile, updated);
    return { changed: true, path: ROOT_INDEX_PATH };
  }

  return { changed: false, path: ROOT_INDEX_PATH };
}

export async function checkRepository(rootDir) {
  const { entries, diagnostics } = await readOkfEntries(rootDir);
  const indexEntry = entries.find((entry) => entry.path === ROOT_INDEX_PATH);

  if (!indexEntry) {
    diagnostics.push(
      diagnostic(
        ROOT_INDEX_PATH,
        1,
        "root index.md が Git 管理下にありません。作成して git add してください",
      ),
    );
    return { valid: false, diagnostics };
  }

  if (indexEntry.valid && diagnostics.length === 0) {
    const actual = extractGeneratedSection(indexEntry.source);
    if (actual === null) {
      diagnostics.push(
        diagnostic(
          ROOT_INDEX_PATH,
          1,
          `生成領域のマーカーがありません: ${GENERATED_BEGIN} / ${GENERATED_END}`,
        ),
      );
    } else {
      const expected = renderGeneratedIndex(entries);
      if (actual !== expected) {
        diagnostics.push(
          diagnostic(
            ROOT_INDEX_PATH,
            1,
            "タグ・文書インデックスが古いか内容と一致しません。`npm run docs:index` を実行してください",
          ),
        );
      }
    }
  }

  return { valid: diagnostics.length === 0, diagnostics };
}

async function main() {
  const command = process.argv[2] ?? "check";
  const rootDir = resolve(process.cwd());

  try {
    if (command === "index") {
      const result = await updateIndex(rootDir);
      console.log(
        result.changed
          ? `root ${ROOT_INDEX_PATH} を更新しました`
          : `root ${ROOT_INDEX_PATH} は最新です`,
      );
      return;
    }

    if (command !== "check") {
      console.error(
        `不明なコマンドです: ${command}（index または check を指定してください）`,
      );
      process.exitCode = 2;
      return;
    }

    const result = await checkRepository(rootDir);
    if (!result.valid) {
      for (const error of result.diagnostics) {
        console.error(formatDiagnostic(error));
      }
      process.exitCode = 1;
      return;
    }

    console.log("OKF 文書と root index の検証に成功しました");
  } catch (error) {
    if (Array.isArray(error.diagnostics)) {
      for (const item of error.diagnostics) {
        console.error(formatDiagnostic(item));
      }
    } else {
      console.error(error.message);
    }
    process.exitCode = 1;
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await main();
}
