import fs from "node:fs";
import path from "node:path";

import { api, apiText } from "./api.js";
import {
  accountToken, agileDir, getLedger, saveLedger, stashDir,
} from "./config.js";
import { cmpVersions, sha256Text } from "./util.js";

function requireAccount() {
  const token = accountToken();
  if (!token) {
    throw new Error("发布模块需要账号凭证:请先运行 `gesellschaft login`");
  }
  return token;
}

function stashFile(slug, version) {
  return path.join(stashDir(), `${slug}-${version}.py`);
}

function findStashFile(slug) {
  const dir = stashDir();
  if (!fs.existsSync(dir)) return null;
  const hit = fs.readdirSync(dir).find((f) => f.startsWith(`${slug}-`) && f.endsWith(".py"));
  return hit ? path.join(dir, hit) : null;
}

function downloadToStash(slug, version = "latest") {
  return api("GET", `/modules/${encodeURIComponent(slug)}/source?version=${version}`,
    { raw: true }).then(async (resp) => {
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
    }
    const source = await resp.text();
    const sha = resp.headers.get("x-module-sha256");
    const ver = resp.headers.get("x-module-version") || version;
    const actual = sha256Text(source);
    if (sha && actual !== sha) {
      throw new Error(`sha256 校验失败(期望 ${sha},实际 ${actual}),已放弃保存`);
    }
    fs.mkdirSync(stashDir(), { recursive: true });
    const file = stashFile(slug, ver);
    fs.writeFileSync(file, source, "utf-8");
    return { file, version: ver, sha: actual };
  });
}

export function registerAgile(prog) {
  const agile = prog.command("agile").description("Agile Module 市场与暂存区管理");

  agile
    .command("find")
    .description("查询云端 Agile Module")
    .argument("[query]", "关键词(匹配 id/描述/用法,留空列出全部)")
    .action(async (query) => {
      const q = query ? `?q=${encodeURIComponent(query)}` : "";
      console.log(await apiText("GET", "/modules" + q));
    });

  agile
    .command("list")
    .description("查看本机已批准安装的 Agile Module")
    .action(() => {
      const ledger = getLedger();
      const ids = Object.keys(ledger);
      if (!ids.length) return console.log("(本机暂无已安装模块)");
      for (const id of ids) {
        console.log(`${id} v${ledger[id].version} → ${ledger[id].file}`);
      }
    });

  agile
    .command("add")
    .description("下载模块到暂存区(不自动启用,请先审阅源码)")
    .argument("<slug>", "模块 id")
    .action(async (slug) => {
      const { file, version, sha } = await downloadToStash(slug);
      console.log(`已下载 ${slug} v${version} 到暂存区:`);
      console.log("  " + file);
      console.log(`sha256: ${sha}`);
      console.log("安全提示:请先 `gesellschaft agile stash view " + slug +
        "` 完整审阅源码,再执行 `gesellschaft agile stash approve " + slug + "` 启用。");
    });

  const stash = agile.command("stash").description("暂存区操作");

  stash
    .command("view")
    .description("查看暂存区中模块的完整源码(Agent 投入使用前必须先读取)")
    .argument("<slug>", "模块 id")
    .action((slug) => {
      const file = findStashFile(slug);
      if (!file) throw new Error(`暂存区中没有 ${slug},请先 agile add`);
      console.log(`# 文件: ${file}`);
      console.log(fs.readFileSync(file, "utf-8"));
    });

  stash
    .command("approve")
    .description("审阅通过后,把模块安装到 faustbot 的 Agile 目录")
    .argument("<slug>", "模块 id")
    .action((slug) => {
      const file = findStashFile(slug);
      if (!file) throw new Error(`暂存区中没有 ${slug},请先 agile add`);
      const source = fs.readFileSync(file, "utf-8");
      const version = path.basename(file, ".py").slice(slug.length + 1);
      fs.mkdirSync(agileDir(), { recursive: true });
      const target = path.join(agileDir(), `${slug}.py`);
      fs.copyFileSync(file, target);
      const ledger = getLedger();
      ledger[slug] = {
        version,
        file: target,
        sha256: sha256Text(source),
        approved_at: new Date().toISOString(),
      };
      saveLedger(ledger);
      console.log(`已安装 ${slug} v${version} → ${target}`);
      console.log("提示: 在 FaustBot 中执行 agileOperate(load, " + slug + ") 加载。");
    });

  stash
    .command("rm")
    .description("丢弃暂存区中的模块(拒绝安装时使用)")
    .argument("<slug>", "模块 id")
    .action((slug) => {
      const file = findStashFile(slug);
      if (file) fs.unlinkSync(file);
      console.log(`已从暂存区移除 ${slug}。`);
    });

  agile
    .command("upgrade")
    .description("检查并下载更新(新版本进入暂存区,审阅后 approve 生效)")
    .argument("[slug]", "只升级指定模块;留空检查全部")
    .action(async (slug) => {
      const ledger = getLedger();
      const ids = slug ? [slug] : Object.keys(ledger);
      if (!ids.length) return console.log("(本机没有已安装模块,无可升级)");
      for (const id of ids) {
        const local = ledger[id];
        if (!local) {
          console.log(`${id}: 本机未安装,跳过(先 agile add)`);
          continue;
        }
        const meta = await api("GET", `/modules/${encodeURIComponent(id)}`);
        const latest = meta.module.latest_version;
        if (cmpVersions(latest, local.version) <= 0) {
          console.log(`${id}: 已是最新(v${local.version})`);
          continue;
        }
        const { file, version } = await downloadToStash(id, "latest");
        console.log(`${id}: v${local.version} → v${version} 已下载到 ${file}`);
        console.log(`  审阅后执行: gesellschaft agile stash approve ${id}`);
      }
    });

  agile
    .command("publish")
    .description("发布 Agile Module 到云端")
    .requiredOption("--file <path>", "模块 .py 文件路径")
    .requiredOption("--id <slug>", "全局唯一的模块 id")
    .requiredOption("--description <text>", "一句话描述")
    .requiredOption("--usage <text>", "用法说明")
    .option("--version <semver>", "显式版本号(缺省自动 patch+1)")
    .option("--no-announce", "不在论坛发布通告帖")
    .action(async (opts) => {
      const token = requireAccount();
      if (!fs.existsSync(opts.file)) throw new Error(`文件不存在: ${opts.file}`);
      if (!opts.file.endsWith(".py")) throw new Error("模块必须是 .py 文件");
      const source = fs.readFileSync(opts.file, "utf-8");
      const form = new FormData();
      form.append("slug", opts.id);
      form.append("description", opts.description);
      form.append("usage_text", opts.usage);
      if (opts.version) form.append("version", opts.version);
      if (!opts.announce) form.append("no_announce", "true");
      form.append("file", new Blob([source], { type: "text/x-python" }),
        path.basename(opts.file));
      const r = await api("POST", "/modules", { token, form });
      console.log(`已发布 ${r.slug} v${r.version}`);
      console.log(`sha256: ${r.sha256}`);
      if (r.announce_thread_id) {
        console.log(`通告帖: 帖子#${r.announce_thread_id}`);
      }
    });

  agile
    .command("list-published")
    .description("查看我发布到云端的模块")
    .action(async () => {
      const token = requireAccount();
      console.log(await apiText("GET", "/modules?mine=true", { token }));
    });
}
