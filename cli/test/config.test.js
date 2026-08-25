import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

process.env.GESSELLSCHAFT_HOME = fs.mkdtempSync(
  path.join(os.tmpdir(), "ges-test-")
);

const { setServer, getServer, saveCredentials, getCredentials, getLedger, saveLedger } =
  await import("../src/config.js");
const { cmpVersions, sha256Text } = await import("../src/util.js");

test("set-server / get-server 往返并去掉尾部斜杠", () => {
  setServer("http://127.0.0.1:8787/");
  assert.equal(getServer(), "http://127.0.0.1:8787");
  assert.equal(getServer(), "http://127.0.0.1:8787");
});

test("凭证保存与读取", () => {
  saveCredentials({ accountToken: "GLA-abc", agentToken: "GLS-def" });
  const creds = getCredentials();
  assert.equal(creds.accountToken, "GLA-abc");
  assert.equal(creds.agentToken, "GLS-def");
});

test("模块账本读写", () => {
  const ledger = getLedger();
  ledger["demo-mod"] = { version: "1.0.0", file: "/tmp/x.py" };
  saveLedger(ledger);
  assert.equal(getLedger()["demo-mod"].version, "1.0.0");
});

test("semver 比较", () => {
  assert.ok(cmpVersions("1.0.1", "1.0.0") > 0);
  assert.ok(cmpVersions("1.0.0", "1.0.1") < 0);
  assert.equal(cmpVersions("2.0.0", "2.0.0"), 0);
  assert.ok(cmpVersions("0.9.9", "1.0.0") < 0);
  assert.ok(cmpVersions("1.10.0", "1.9.0") > 0);
});

test("sha256Text 与服务器端 sha256_hex 一致", () => {
  assert.equal(sha256Text("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
});
