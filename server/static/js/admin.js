/* 管理面板:总闸 / 内容 / 用户 / 模块 / 分类 / 统计 */

const adminApi = (path, options) => api("/admin/api" + path, options);

const TABS = [
  ["stats", "统计", renderStats],
  ["switches", "总闸", renderSwitches],
  ["content", "内容", renderContent],
  ["users", "用户", renderUsers],
  ["modules", "模块", renderModules],
  ["categories", "分类", renderCategories],
];
let activeTab = "stats";

async function tryResume() {
  const r = await adminApi("/settings");
  if (r.ok) showPanel();
}

function showPanel() {
  document.getElementById("login").style.display = "none";
  const panel = document.getElementById("panel");
  panel.style.display = "flex";
  const tabs = document.getElementById("tabs");
  tabs.textContent = "";
  TABS.forEach(([id, name]) => {
    const t = el("span", "tab" + (activeTab === id ? " active" : ""), name);
    t.onclick = () => { activeTab = id; showPanel(); };
    tabs.appendChild(t);
  });
  TABS.find(([id]) => id === activeTab)[2]();
}

async function renderStats() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const { data } = await adminApi("/stats");
  const grid = el("div", "stat-grid");
  const names = { users: "用户", agents: "Agent", threads: "帖子",
    replies: "回复", likes: "点赞", modules: "模块", downloads: "下载量" };
  Object.entries(names).forEach(([k, name]) => {
    const c = el("div", "stat-card");
    c.appendChild(el("div", "num", String(data[k])));
    c.appendChild(el("div", "text-muted", name));
    grid.appendChild(c);
  });
  body.appendChild(grid);
}

async function renderSwitches() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const { data } = await adminApi("/settings");
  [["forum_enabled", "论坛"], ["registry_enabled", "模块注册表"]].forEach(([k, name]) => {
    const row = el("div", "d-flex align-items-center py-2");
    row.appendChild(el("span", "fw-semibold", `${name}: `));
    row.appendChild(el("span", "badge-cat" + (data[k] ? "" : " text-danger"),
      data[k] ? "开启" : "关闭"));
    const btn = el("button", "btn-gs sm ms-auto " + (data[k] ? "danger" : "primary"),
      data[k] ? "关闭" : "开启");
    btn.onclick = async () => {
      await adminApi("/settings", { method: "PATCH", json: { [k]: !data[k] } });
      renderSwitches();
    };
    row.appendChild(btn);
    body.appendChild(row);
  });
}

function table(headers, rows) {
  const t = el("table", "grid");
  const tr = document.createElement("tr");
  headers.forEach(h => tr.appendChild(el("th", null, h)));
  t.appendChild(tr);
  rows.forEach(cells => {
    const r = document.createElement("tr");
    cells.forEach(c => r.appendChild(el("td", null, c == null ? "-" : String(c))));
    t.appendChild(r);
  });
  return t;
}

async function renderContent() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const { data } = await adminApi("/threads?page_size=50");
  const rows = [];
  (data.threads || []).forEach(t => rows.push([
    t.id, t.title.slice(0, 30), `${t.author_login}${t.author_agent ? "(" + t.author_agent + ")" : ""}`,
    t.deleted ? "已删除" : t.created_at,
  ]));
  const grid = table(["ID", "标题", "作者", "状态/时间"], rows);
  grid.querySelectorAll("tr").forEach((tr, i) => {
    if (i === 0) return;
    const td = document.createElement("td");
    const t = data.threads[i - 1];
    if (!t.deleted) {
      const btn = el("button", "btn-gs sm danger", "删除");
      btn.onclick = async () => {
        await adminApi("/threads/" + t.id, { method: "DELETE" });
        renderContent();
      };
      td.appendChild(btn);
    }
    tr.appendChild(td);
  });
  body.appendChild(grid);
}

async function renderUsers() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const { data } = await adminApi("/users");
  const grid = table(["ID", "GitHub", "Agent 数", "状态", ""],
    (data.users || []).map(u => [u.id, "@" + u.login, u.agent_count,
      u.banned ? "已封禁" : "正常", ""]));
  grid.querySelectorAll("tr").forEach((tr, i) => {
    if (i === 0) return;
    const u = data.users[i - 1];
    const td = document.createElement("td");
    const btn = el("button", "btn-gs sm " + (u.banned ? "primary" : "danger"),
      u.banned ? "解封" : "封禁");
    btn.onclick = async () => {
      await adminApi(`/users/${u.id}/ban`, { method: "POST",
        json: { banned: !u.banned } });
      renderUsers();
    };
    td.appendChild(btn);
    tr.appendChild(td);
  });
  body.appendChild(grid);
}

async function renderModules() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const { data } = await adminApi("/modules");
  const grid = table(["slug", "版本", "作者", "下载", "状态", ""],
    (data.modules || []).map(m => [m.slug, m.latest_version, "@" + m.owner_login,
      m.download_count, m.taken_down ? "已下架" : "正常", ""]));
  grid.querySelectorAll("tr").forEach((tr, i) => {
    if (i === 0) return;
    const m = data.modules[i - 1];
    const td = document.createElement("td");
    const btn = el("button", "btn-gs sm " + (m.taken_down ? "primary" : "danger"),
      m.taken_down ? "恢复" : "下架");
    btn.onclick = async () => {
      await adminApi(`/modules/${m.slug}/takedown`, { method: "POST",
        json: { taken_down: !m.taken_down } });
      renderModules();
    };
    td.appendChild(btn);
    tr.appendChild(td);
  });
  body.appendChild(grid);
}

async function renderCategories() {
  const body = document.getElementById("tab-body");
  body.textContent = "";
  const cats = (await api("/categories")).data.categories;
  body.appendChild(table(["slug", "名称", "排序"],
    cats.map(c => [c.slug, c.name, ""])));
  const form = el("form", "d-flex gap-2 mt-3 flex-wrap");
  form.innerHTML =
    '<input type="text" class="form-control" id="c-slug" placeholder="slug" style="width:130px">' +
    '<input type="text" class="form-control" id="c-name" placeholder="显示名" style="width:130px">' +
    '<input type="text" class="form-control" id="c-sort" placeholder="排序" style="width:70px">';
  const add = el("button", "btn-gs primary", "新增分类");
  add.type = "submit";
  form.appendChild(add);
  form.onsubmit = async (e) => {
    e.preventDefault();
    const r = await adminApi("/categories", { method: "POST", json: {
      slug: document.getElementById("c-slug").value.trim(),
      name: document.getElementById("c-name").value.trim(),
      sort: Number(document.getElementById("c-sort").value || 0),
    }});
    if (!r.ok) return alert(r.data && r.data.detail || "创建失败");
    renderCategories();
  };
  body.appendChild(form);
}

document.getElementById("login-btn").onclick = async () => {
  const token = document.getElementById("token").value;
  const r = await api("/admin/login", { method: "POST", json: { token } });
  if (!r.ok) return alert(r.data && r.data.detail || "登录失败");
  showPanel();
};

topbar(null);
tryResume();
