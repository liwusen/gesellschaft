/* Gesellschaft 前端公共工具(仿 Configer 的轻量 DOM 助手) */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function api(path, options) {
  options = options || {};
  options.credentials = "include";
  if (options.json) {
    options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers);
    options.body = JSON.stringify(options.json);
  }
  const resp = await fetch(path, options);
  let data = null;
  try { data = await resp.json(); } catch (e) { /* 非 JSON 响应 */ }
  return { ok: resp.ok, status: resp.status, data };
}

function topbar(active) {
  const bar = el("div", "topbar");
  const brand = el("a", "brand", "Gesellschaft");
  brand.href = "/";
  bar.appendChild(brand);
  const nav = el("nav");
  [["/", "论坛"], ["/modules", "模块市场"], ["/me", "我的"]].forEach(([href, name]) => {
    const a = el("a", null, name);
    a.href = href;
    if (active === href) a.style.fontWeight = "600";
    nav.appendChild(a);
  });
  bar.appendChild(nav);
  const spacer = el("div", "spacer");
  bar.appendChild(spacer);
  api("/me/session").then(({ data }) => {
    const user = data && data.user;
    if (user) {
      const a = el("a", null, "@" + user.login);
      a.href = "/me";
      bar.appendChild(a);
    } else {
      const a = el("a", null, "GitHub 登录");
      a.href = "/login";
      bar.appendChild(a);
    }
  });
  document.body.prepend(bar);
}

function threadItem(t) {
  const item = el("div", "thread-item");
  const title = el("a", "title", t.title);
  title.href = "/thread/" + t.id;
  item.appendChild(title);
  item.appendChild(el("div", "muted",
    `${t.author} · ${t.category_name} · 赞 ${t.like_count} · 回复 ${t.reply_count} · ${t.created_at}`));
  return item;
}
