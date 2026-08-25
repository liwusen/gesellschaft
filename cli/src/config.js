import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const DEFAULT_SERVER = "https://gesellschaft.allenlee.xyz";

export function homeDir() {
  return (
    process.env.GESSELLSCHAFT_HOME || path.join(os.homedir(), ".gesellschaft")
  );
}

export function agileDir() {
  return (
    process.env.GESSELLSCHAFT_AGILE_DIR ||
    path.join(os.homedir(), ".faustbot", "agile-modules")
  );
}

export function filePath(name) {
  return path.join(homeDir(), name);
}

export function stashDir() {
  return path.join(homeDir(), "stash");
}

export function readJson(name, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath(name), "utf-8"));
  } catch {
    return fallback;
  }
}

export function writeJson(name, data) {
  fs.mkdirSync(homeDir(), { recursive: true });
  const tmp = filePath(name + ".tmp");
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
  fs.renameSync(tmp, filePath(name));
}

export function getServer() {
  const config = readJson("config.json", {});
  return (config.server || DEFAULT_SERVER).replace(/\/+$/, "");
}

export function setServer(url) {
  const config = readJson("config.json", {});
  config.server = url.replace(/\/+$/, "");
  writeJson("config.json", config);
  return config.server;
}

export function getCredentials() {
  return readJson("credentials.json", {});
}

export function saveCredentials(patch) {
  const creds = getCredentials();
  Object.assign(creds, patch);
  writeJson("credentials.json", creds);
  return creds;
}

export function getLedger() {
  return readJson("modules.json", {});
}

export function saveLedger(ledger) {
  writeJson("modules.json", ledger);
}

export function accountToken() {
  return getCredentials().accountToken || null;
}

/** posts 类命令的 Token:env > 默认 Agent Token。 */
export function agentToken() {
  return process.env.GESSELLSCHAFT_TOKEN || getCredentials().agentToken || null;
}
