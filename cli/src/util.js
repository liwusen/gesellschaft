import crypto from "node:crypto";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "path";

export function cmpVersions(a, b) {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) - (pb[i] || 0);
  }
  return 0;
}

export function sha256File(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

export function sha256Text(text) {
  return crypto.createHash("sha256").update(text, "utf-8").digest("hex");
}

function openBrowser(url) {
  if (process.env.GESSELLSCHAFT_NO_BROWSER) return;
  if (process.platform === "win32") {
    spawn("cmd", ["/c", "start", "", url], { detached: true, shell: false }).unref();
  } else if (process.platform === "darwin") {
    spawn("open", [url], { detached: true }).unref();
  } else {
    spawn("xdg-open", [url], { detached: true }).unref();
  }
}

/**
 * GitHub OAuth 登录:本地起 loopback 监听 → 打开浏览器 → 服务器中转交换 → 收 Token。
 * @returns {Promise<string>} account token
 */
export function loginFlow(serverUrl, timeoutMs = 300_000) {
  return new Promise((resolve, reject) => {
    const nonce = crypto.randomBytes(8).toString("hex");
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, "http://127.0.0.1");
      if (url.pathname !== "/callback") {
        res.writeHead(404).end();
        return;
      }
      if (url.searchParams.get("nonce") !== nonce) {
        res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("nonce 校验失败,请重新运行 gesellschaft login");
        return;
      }
      const token = url.searchParams.get("account_token");
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end("<h2>登录成功</h2><p>Token 已保存到本机,可以关闭此页面。</p>");
      server.closeAllConnections?.();
      server.close(() => resolve(token));
    });
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      const startUrl =
        `${serverUrl}/oauth/cli/start?port=${port}&nonce=${nonce}`;
      console.log("浏览器已打开授权页面,如未弹出请手动访问:\n  " + startUrl);
      openBrowser(startUrl);
    });
    setTimeout(() => {
      server.close(() => reject(new Error("登录超时(5 分钟)")));
    }, timeoutMs).unref?.();
  });
}

export function pathJoin(...parts) {
  return path.join(...parts);
}
