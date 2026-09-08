import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

let repositoryRoot;

try {
  repositoryRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], {
    encoding: "utf8",
  }).trim();
} catch {
  console.log("Not a Git repository; skipping Git hook setup.");
  process.exit(0);
}

if (!existsSync(join(repositoryRoot, ".githooks", "pre-push"))) {
  console.log("No repository-managed Git hooks found; skipping setup.");
  process.exit(0);
}

execFileSync("git", ["config", "--local", "core.hooksPath", ".githooks"], {
  cwd: repositoryRoot,
  stdio: "inherit",
});

console.log("Configured Git hooks path: .githooks");
