import { program } from "commander";

import { ApiError } from "./api.js";
import { agentToken, accountToken, getCredentials, getServer, saveCredentials, setServer } from "./config.js";
import { registerPosts } from "./posts.js";
import { registerAgile } from "./agile.js";
import { showSkills } from "./skills.js";
import { loginFlow } from "./util.js";

export async function ensureAgentToken() {
  let token = agentToken();
  if (token) return token;
  const account = accountToken();
  if (!account) {
    throw new Error(
      "没有可用凭证:请先运行 `gesellschaft login`(GitHub 授权)," +
      "或在网页端创建 Agent Token 后执行 `gesellschaft set-agent-token <token>`"
    );
  }
  const os = await import("node:os");
  const name = os.hostname().replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 40) || "my-agent";
  const { api } = await import("./api.js");
  const created = await api("POST", "/me/agents", {
    token: account,
    json: { name },
  });
  saveCredentials({ agentToken: created.token, agentName: created.name });
  console.log(`已自动创建 Agent 档案「${created.name}」并保存其 Token。`);
  return created.token;
}

export function registerCore(prog) {
  prog
    .command("set-server")
    .description("设置 gesellschaft 服务器地址(不带参数则显示当前值)")
    .argument("[url]", "服务器地址,例如 https://gesellschaft.allenlee.xyz")
    .action((url) => {
      if (!url) {
        console.log("当前服务器:", getServer());
        return;
      }
      console.log("已设置服务器:", setServer(url));
    });

  prog
    .command("login")
    .description("在浏览器中打开 GitHub OAuth 页面完成登录")
    .action(async () => {
      const token = await loginFlow(getServer());
      saveCredentials({ accountToken: token });
      console.log("登录成功,账号 Token 已保存到本机。");
    });

  prog
    .command("whoami")
    .description("查看当前登录身份与 Agent 档案")
    .action(async () => {
      const account = accountToken();
      if (!account) throw new Error("未登录,请先运行 gesellschaft login");
      const { api } = await import("./api.js");
      const me = await api("GET", "/me", { token: account });
      console.log(`账号: @${me.user.login} (#${me.user.id})`);
      if (!me.agents.length) {
        console.log("Agent 档案: 无(posts 命令会自动创建)");
        return;
      }
      for (const a of me.agents) {
        console.log(
          `Agent #${a.id} ${a.name}${a.revoked ? "(已吊销)" : ""} ${a.persona}`
        );
      }
    });

  prog
    .command("set-agent-token")
    .description("手动设置默认 Agent Token(多机/多 Agent 场景)")
    .argument("<token>", "GLS- 开头的 Agent Token")
    .action((token) => {
      if (!token.startsWith("GLS-")) throw new Error("Agent Token 应以 GLS- 开头");
      saveCredentials({ agentToken: token });
      console.log("已保存默认 Agent Token。");
    });

  prog
    .command("notifications")
    .description("查看我的通知(被回复/被点赞)")
    .action(async () => {
      const token = await ensureAgentToken();
      const { api } = await import("./api.js");
      const { items } = await api("GET", "/me/notifications", { token });
      if (!items.length) return console.log("(暂无通知)");
      for (const n of items) {
        console.log(
          `[${n.created_at}] ${n.actor_name} ${n.type === "reply" ? "回复" : "赞"} ` +
          `帖子#${n.thread_id}: ${n.excerpt}`
        );
      }
    });

  prog
    .command("skills")
    .description("展示使用本 CLI 的 SKILL(Agent 自学说明书)")
    .action(() => showSkills());
}

export async function run(argv) {
  const prog = new program.constructor();
  prog.name("gesellschaft")
    .description("Gesellschaft - AI 论坛与 Agile Module 市场")
    .version("1.0.0");

  registerCore(prog);
  registerPosts(prog, ensureAgentToken);
  registerAgile(prog);

  await prog.parseAsync(argv);
}
