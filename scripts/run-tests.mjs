import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
const result = spawnSync(
  existsSync(python) ? python : "python",
  ["-m", "unittest", "discover", "-s", "companion/tests", "-v"],
  { stdio: "inherit" },
);
process.exit(result.status ?? 1);
