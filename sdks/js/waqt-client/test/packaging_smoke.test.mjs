// test/packaging_smoke.test.mjs — proves waqt-client is actually
// packageable and installable on its own: runs `npm pack` to build the
// real tarball, installs it into a throwaway directory (no access to
// this checkout's source tree), and imports/exercises it from there.
// Closes the "clean-install package tests" item in Sprint 10's Required
// tests list. Network-free (installs a local tarball).

import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.resolve(__dirname, "..");

test("npm pack + clean install into a fresh directory works end to end", { timeout: 60_000 }, async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "waqt-client-pack-"));
  try {
    const packOut = execFileSync("npm", ["pack", "--silent", "--pack-destination", tmp], {
      cwd: PKG_ROOT, encoding: "utf8",
    }).trim();
    const tarball = path.join(tmp, packOut.split("\n").pop());
    assert.ok(fs.existsSync(tarball), `expected tarball at ${tarball}`);

    const installDir = fs.mkdtempSync(path.join(os.tmpdir(), "waqt-client-install-"));
    fs.writeFileSync(path.join(installDir, "package.json"), JSON.stringify({ name: "smoke-test", version: "0.0.0", type: "module" }));
    execFileSync("npm", ["install", "--silent", tarball], { cwd: installDir, encoding: "utf8" });

    const smokeScript = `
      import { WaqtClient, requests, VERSION } from "waqt-client";
      if (VERSION !== "0.2.0") throw new Error("unexpected VERSION " + VERSION);
      const req = requests.scheduleResolveRequest({ lat: 9.0192, lon: 38.7525, operation: requests.nextEventOp() });
      const body = req.toJSON();
      const expected = JSON.stringify({ location: { lat: 9.0192, lon: 38.7525, elevation_m: 0.0 }, operation: { op: "next_event" } });
      if (JSON.stringify(body) !== expected) throw new Error("unexpected body " + JSON.stringify(body));
      if (typeof WaqtClient !== "function") throw new Error("WaqtClient not exported");
      console.log("SMOKE OK");
    `;
    const smokeFile = path.join(installDir, "smoke.mjs");
    fs.writeFileSync(smokeFile, smokeScript);
    const result = execFileSync("node", [smokeFile], { cwd: installDir, encoding: "utf8" });
    assert.match(result, /SMOKE OK/);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});
