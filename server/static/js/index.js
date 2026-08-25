/* 首页:分类筛选 + 帖子列表 + 分页 + 发帖 */

let state = { category: "", page: 1, totalPages: 1 };

async function loadChips() {
  const { data } = await api("/categories");
  const chips = document.getElementById("chips");
  chips.appendChild(chip("全部", ""));
  (data.categories || []).forEach(c => chips.appendChild(chip(c.name, c.slug)));
}

function chip(name, slug) {
  const c = el("span", "chip" + (state.category === slug ? " active" : ""), name);
  c.onclick = () => {
    state.category = slug; state.page = 1;
    [...document.getElementById("chips").children]
      .forEach(x => x.classList.remove("active"));
    c.classList.add("active");
    load();
  };
  return c;
}

async function load() {
  const q = new URLSearchParams({ page: state.page, page_size: 20 });
  if (state.category) q.set("category", state.category);
  const { ok, status, data } = await api("/threads?" + q.toString());
  const list = document.getElementById("list");
  list.textContent = "";
  if (!ok) {
    list.appendChild(el("div", "empty", status === 403 ? "论坛已关闭。" : "加载失败。"));
    return;
  }
  document.getElementById("stat-total").textContent = data.total;
  if (!data.threads.length) list.appendChild(el("div", "empty", "(暂无帖子)"));
  data.threads.forEach(t => list.appendChild(threadItem(t)));
  state.totalPages = Math.max(1, Math.ceil(data.total / 20));
  document.getElementById("pageinfo").textContent =
    `第 ${data.page} / ${state.totalPages} 页 · 共 ${data.total} 帖`;
}

document.getElementById("prev").onclick = () => {
  if (state.page > 1) { state.page--; load(); }
};
document.getElementById("next").onclick = () => {
  if (state.page < state.totalPages) { state.page++; load(); }
};

async function initComposer() {
  const sel = document.getElementById("t-category");
  const { data } = await api("/categories");
  (data.categories || []).forEach(c => {
    const opt = el("option", null, c.name);
    opt.value = c.slug;
    sel.appendChild(opt);
  });
  const session = (await api("/me/session")).data;
  if (!session.user) {
    const btn = document.getElementById("t-post");
    btn.textContent = "登录后发帖";
    btn.onclick = () => location.href = "/oauth/web/start?next=/";
    document.getElementById("t-title").disabled = true;
    document.getElementById("t-content").disabled = true;
    return;
  }
  document.getElementById("t-post").onclick = async () => {
    const title = document.getElementById("t-title").value.trim();
    const content = document.getElementById("t-content").value.trim();
    if (!title || !content) return alert("标题和正文不能为空");
    const r = await api("/threads", {
      method: "POST",
      json: { title, content, category: sel.value },
    });
    if (!r.ok) return alert(r.data && r.data.detail || "发布失败");
    location.href = "/thread/" + r.data.id;
  };
}

topbar("/");
loadChips().then(load).then(initComposer);
