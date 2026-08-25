/* 模块市场:搜索 + 列表 + 分页 */

let page = 1, totalPages = 1, q = "";

async function load() {
  const params = new URLSearchParams({ page, page_size: 20 });
  if (q) params.set("q", q);
  const { ok, data } = await api("/modules?" + params.toString());
  const list = document.getElementById("list");
  list.textContent = "";
  if (!ok) {
    list.appendChild(el("div", "muted", "模块注册表已关闭。"));
    return;
  }
  if (!data.modules.length) list.appendChild(el("div", "muted", "(暂无模块)"));
  data.modules.forEach(m => {
    const item = el("div", "thread-item");
    const title = el("a", "title",
      `${m.slug} v${m.latest_version}`);
    title.href = "/module/" + m.slug;
    item.appendChild(title);
    item.appendChild(el("div", null, m.description || ""));
    item.appendChild(el("div", "muted",
      `作者 ${m.owner_login} · 下载 ${m.download_count} · ${m.created_at}`));
    list.appendChild(item);
  });
  totalPages = Math.max(1, Math.ceil(data.total / 20));
  document.getElementById("pageinfo").textContent =
    `第 ${data.page} / ${totalPages} 页 · 共 ${data.total} 个`;
}

document.getElementById("search").onclick = () => {
  q = document.getElementById("q").value.trim();
  page = 1;
  load();
};
document.getElementById("prev").onclick = () => { if (page > 1) { page--; load(); } };
document.getElementById("next").onclick = () => { if (page < totalPages) { page++; load(); } };

topbar("/modules");
load();
