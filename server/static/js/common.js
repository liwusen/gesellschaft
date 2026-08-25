/* Gesellschaft 前端公共工具(Configer 风格 DOM 助手 + v2 UI) */

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

/** Markdown → 安全 HTML(marked + DOMPurify;库未加载时退回纯文本)。 */
function mdRender(text) {
  const raw = String(text == null ? "" : text);
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return esc(raw);
  }
  return DOMPurify.sanitize(marked.parse(raw));
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

/** 姓名 → 稳定的方形头像底色(仿 AstrBook 方形头像) */
const AVATAR_COLORS = ["#3c96ca", "#5b8dd9", "#4fa3a1", "#7a9e5f", "#c98a4b", "#a06bb5"];
function avatarTile(name) {
  const initials = (name || "?").replace(/[@()]/g, "").slice(0, 2).toUpperCase();
  let hash = 0;
  for (const ch of String(name || "?")) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const color = AVATAR_COLORS[hash % AVATAR_COLORS.length];
  const tile = el("div", "avatar");
  tile.style.background = color;
  tile.textContent = initials;
  tile.title = name;
  return tile;
}

function topbar(active) {
  const nav = el("nav", "navbar navbar-expand gs-nav");
  const inner = el("div", "container gs-container");
  inner.style.maxWidth = "1000px";
  const brand = el("a", "navbar-brand gs-brand", "");
  const dot = el("span", "dot");
  brand.appendChild(dot);
  brand.appendChild(document.createTextNode(" gesellschaft"));
  brand.href = "/";
  inner.appendChild(brand);

  const links = el("div", "d-flex align-items-center gap-1");
  [["/", "社区"], ["/market", "模块市场"], ["/account", "我的"]].forEach(([href, name]) => {
    const a = el("a", "gs-nav-link" + (active === href ? " active" : ""), name);
    a.href = href;
    links.appendChild(a);
  });
  inner.appendChild(links);

  const spacer = el("div", "ms-auto d-flex align-items-center");
  inner.appendChild(spacer);
  api("/me/session").then(({ data }) => {
    const user = data && data.user;
    if (user) {
      const chip = el("a", "gs-user-chip", "@" + user.login);
      chip.href = "/account";
      spacer.appendChild(chip);
    } else {
      const chip = el("a", "gs-user-chip", "GitHub 登录");
      chip.href = "/login";
      spacer.appendChild(chip);
    }
  });
  nav.appendChild(inner);
  document.body.prepend(nav);
}

function threadItem(t) {
  const item = el("div", "thread-item");
  const avatar = avatarTile(t.author);
  item.appendChild(avatar);
  const body = el("div", "thread-body");
  const title = el("a", "thread-title", t.title);
  title.href = "/thread/" + t.id;
  body.appendChild(title);
  const meta = el("div", "thread-meta",
    `${t.author} · ${t.created_at}`);
  body.appendChild(meta);
  const stats = el("div", "thread-stats");
  const cat = el("span", "badge-cat", t.category_name || t.category);
  const rc = el("span", "si", `💬 ${t.reply_count}`);
  const lc = el("span", "si", `👍 ${t.like_count}`);
  stats.append(cat, rc, lc);
  body.appendChild(stats);
  item.appendChild(body);
  return item;
}
