/* 模块详情:元信息、版本表、安装命令 */

const slug = decodeURIComponent(location.pathname.split("/").pop());

async function load() {
  const { ok, status, data } = await api("/modules/" + encodeURIComponent(slug));
  const box = document.getElementById("detail");
  if (!ok) {
    box.appendChild(el("div", "empty",
      status === 404 ? "模块不存在或已下架。" : "加载失败。"));
    return;
  }
  const m = data.module;
  const head = el("div", "d-flex align-items-start gap-3");
  const avatar = avatarTile(m.slug);
  avatar.style.width = "52px"; avatar.style.height = "52px";
  avatar.style.minWidth = "52px"; avatar.style.fontSize = "20px";
  head.appendChild(avatar);
  const mid = el("div", "flex-grow-1");
  const h3 = el("h3", "fw-bold mb-1");
  h3.append(`${m.slug} `,
    el("span", "badge-cat me-1", `v${m.latest_version}`),
    el("span", "badge-cat", m.license || "MIT"));
  mid.appendChild(h3);
  mid.appendChild(el("div", "text-muted small",
    `作者 @${m.owner_login} · 下载 ${m.download_count} · ${m.created_at}`));
  head.appendChild(mid);
  box.appendChild(head);

  if (m.description) {
    const desc = el("div", "md mt-3");
    desc.innerHTML = mdRender(m.description);
    box.appendChild(desc);
  }
  if (m.usage_text) {
    box.appendChild(el("h6", "fw-bold mt-4 mb-1", "用法"));
    const usage = el("div", "md");
    usage.innerHTML = mdRender(m.usage_text);
    box.appendChild(usage);
  }
  box.appendChild(el("h6", "fw-bold mt-4 mb-1", "安装到本机暂存区"));
  const cmd = el("div", "token-box", `npx gesellschaft agile add ${m.slug}`);
  box.appendChild(cmd);
  if (m.announced_thread_id) {
    const a = el("a", "small d-inline-block mt-2", "查看发布通告帖 →");
    a.href = "/thread/" + m.announced_thread_id;
    box.appendChild(a);
  }
  box.appendChild(el("h6", "fw-bold mt-4 mb-2", "版本"));
  const table = el("table", "grid");
  table.innerHTML = "<tr><th>版本</th><th>sha256</th><th>大小</th><th>时间</th><th>状态</th></tr>";
  (data.versions || []).forEach(v => {
    const tr = document.createElement("tr");
    [v.version, v.sha256.slice(0, 16) + "…", v.size + " B", v.created_at,
     v.taken_down ? "已下架" : (v.version === m.latest_version ? "最新" : "")].forEach(x => {
      const td = document.createElement("td");
      td.textContent = x;
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  box.appendChild(table);
}

topbar("/market");
load();
