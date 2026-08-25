/* 模块详情:元信息、版本表、安装命令 */

const slug = decodeURIComponent(location.pathname.split("/").pop());

async function load() {
  const { ok, status, data } = await api("/modules/" + encodeURIComponent(slug));
  const box = document.getElementById("detail");
  if (!ok) {
    box.appendChild(el("div", "muted",
      status === 404 ? "模块不存在或已下架。" : "加载失败。"));
    return;
  }
  const m = data.module;
  box.appendChild(el("h2", null, `${m.slug} v${m.latest_version}`));
  box.appendChild(el("div", "muted", `作者 @${m.owner_login} · 下载 ${m.download_count}`));
  box.appendChild(el("p", null, m.description || "(无描述)"));
  if (m.usage_text) {
    box.appendChild(el("h3", null, "用法"));
    const pre = el("pre", "token-box", m.usage_text);
    pre.style.whiteSpace = "pre-wrap";
    box.appendChild(pre);
  }
  box.appendChild(el("h3", null, "安装到本机暂存区"));
  const cmd = el("div", "token-box", `npx gesellschaft agile add ${m.slug}`);
  box.appendChild(cmd);
  if (m.announced_thread_id) {
    const a = el("a", null, "发布通告帖");
    a.href = "/thread/" + m.announced_thread_id;
    box.appendChild(a);
  }
  box.appendChild(el("h3", null, "版本"));
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

topbar("/modules");
load();
