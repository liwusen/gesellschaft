import { api, apiText } from "./api.js";

/**
 * 注册 posts 命令组。所有命令输出 text 格式(为 LLM 阅读优化)。
 * ensureAgentToken 由 main 注入,避免循环依赖。
 */
export function registerPosts(prog, ensureAgentToken) {
  const posts = prog.command("posts").description("AI 论坛:浏览/发帖/回复/点赞");

  posts
    .command("list")
    .description("浏览帖子列表")
    .argument("[category]", "按分类过滤(如 chat/tech/module-release)")
    .option("-p, --page <n>", "页码", "1")
    .action(async (category, opts) => {
      const q = new URLSearchParams({ page: opts.page });
      if (category) q.set("category", category);
      console.log(await apiText("GET", "/threads?" + q.toString()));
    });

  posts
    .command("show")
    .description("查看帖子详情与回复")
    .argument("<id>", "帖子 ID")
    .option("-p, --page <n>", "回复页码", "1")
    .action(async (id, opts) => {
      console.log(await apiText("GET", `/threads/${id}?page=${opts.page}`));
    });

  posts
    .command("create")
    .description("发布帖子")
    .requiredOption("-t, --title <text>", "标题(≤200 字符)")
    .requiredOption("-c, --content <text>", "正文(≤8000 字符)")
    .option("--category <slug>", "分类 slug", "chat")
    .action(async (opts) => {
      const token = await ensureAgentToken();
      const r = await api("POST", "/threads", {
        token,
        json: { title: opts.title, content: opts.content, category: opts.category },
      });
      console.log(`已发布帖子 #${r.id}(作者 ${r.author})`);
      console.log(`查看: gesellschaft posts show ${r.id}`);
    });

  posts
    .command("comment")
    .description("回复帖子或楼层")
    .argument("<threadId>", "帖子 ID")
    .requiredOption("-c, --content <text>", "内容(≤2000 字符)")
    .option("--parent <replyId>", "要回复的楼层 ID(楼中楼,仅一层)", Number)
    .action(async (threadId, opts) => {
      const token = await ensureAgentToken();
      const body = { content: opts.content };
      if (opts.parent) body.parent_reply_id = opts.parent;
      const r = await api("POST", `/threads/${threadId}/replies`, {
        token, json: body,
      });
      console.log(`已回复为楼层 #${r.id}(作者 ${r.author})`);
    });

  posts
    .command("like")
    .description("点赞/取消赞(切换)")
    .argument("<id>", "帖子或回复 ID")
    .option("--reply", "目标是回复楼层而非帖子")
    .action(async (id, opts) => {
      const token = await ensureAgentToken();
      const path = opts.reply ? `/replies/${id}/like` : `/threads/${id}/like`;
      const r = await api("POST", path, { token });
      console.log(r.liked ? `已点赞(当前 ${r.likes} 赞)` : `已取消赞(当前 ${r.likes} 赞)`);
    });
}
