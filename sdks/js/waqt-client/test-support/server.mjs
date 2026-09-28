// test/helpers/server.mjs — spawns the real FastAPI app (python3 -m
// uvicorn) as a child process for the JS SDK's live integration tests,
// waits for it to answer /v1/health, and returns a teardown function.
// This is a genuine HTTP round trip end to end (Node fetch -> real
// socket -> real ASGI app), not a mock.

import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import net from "node:net";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");

import fs from "node:fs";

function getPythonCmd() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venvPyWin = path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(venvPyWin)) return venvPyWin;
  const venvPyNix = path.join(REPO_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(venvPyNix)) return venvPyNix;
  return process.platform === "win32" ? "python" : "python3";
}

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
    getPythonCmd(),
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
