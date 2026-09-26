// test/helpers/server.mjs — spawns the real FastAPI app (python3 -m
// uvicorn) as a child process for the JS SDK's live integration tests,
// waits for it to answer /v1/health, and returns a teardown function.
// This is a genuine HTTP round trip end to end (Node fetch -> real
// socket -> real ASGI app), not a mock.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import net from "node:net";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");
const VENV_PYTHON = path.join(
  REPO_ROOT,
  ".venv",
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python"
);
const PYTHON = process.env.WAQT_TEST_PYTHON ?? (
  existsSync(VENV_PYTHON) ? VENV_PYTHON : process.platform === "win32" ? "python" : "python3"
);

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

export async function startServer() {
  const port = await findFreePort();
  const child = spawn(
    PYTHON,
    ["-m", "uvicorn", "waqt.api:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "warning"],
    { cwd: REPO_ROOT, stdio: "ignore" }
  );

  const baseUrl = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 15_000;
  let ready = false;
  while (Date.now() < deadline) {
    try {
      const resp = await fetch(`${baseUrl}/v1/health`);
      if (resp.ok) {
        ready = true;
        break;
      }
    } catch {
      // not up yet
    }
    await sleep(150);
  }
  if (!ready) {
    child.kill();
    throw new Error("waqt-api server did not become ready in time");
  }

  return {
    baseUrl,
    async stop() {
      child.kill();
    },
  };
}
