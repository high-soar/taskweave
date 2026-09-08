import { execFileSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ignoredDirectories = new Set([".git", "node_modules"]);
const typeScriptExtensions = new Set([".ts", ".tsx", ".mts", ".cts"]);

function collectTypeScriptFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filePath = join(directory, entry.name);

    if (entry.isDirectory()) {
      return ignoredDirectories.has(entry.name)
        ? []
        : collectTypeScriptFiles(filePath);
    }

    return typeScriptExtensions.has(filePath.slice(filePath.lastIndexOf(".")))
      ? [filePath]
      : [];
  });
}

const compilerArguments = existsSync("tsconfig.json")
  ? ["--noEmit", "--project", "tsconfig.json"]
  : ["--noEmit", ...collectTypeScriptFiles(".")];

if (compilerArguments.length === 1) {
  console.log("No TypeScript files found; skipping typecheck.");
} else {
  execFileSync("npm", ["exec", "--", "tsc", ...compilerArguments], {
    stdio: "inherit",
  });
}
