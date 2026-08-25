/* 帖子详情:正文、楼中楼回复、点赞、回帖 */

const threadId = Number(location.pathname.split("/").pop());
let loggedIn = false;

function likeBtn(targetType, targetId, count, liked) {
  const btn = el("span", "like-btn" + (liked ? " liked" : ""),
    `♡ ${count}`);
  btn.onclick = async () => {
    const r = await api(`/${targetType}/${targetId}/like`, { method: "POST" });
    if (r.status === 401) return location.href = "/oauth/web/start?next=/thread/" + threadId;
    if (!r.ok) return alert(r.data && r.data.detail || "操作失败");
    btn.textContent = (r.data.liked ? "♥ " : "♡ ") + r.data.likes;
    btn.classList.toggle("liked", r.data.liked);
  };
  return btn;
}

function replyNode(r) {
  const box = el("div", "reply");
  const head = el("div", "r-head");
  const avatar = avatarTile(r.author);
  avatar.classList.add("sm");
  head.appendChild(avatar);
  head.appendChild(el("span", "fw-semibold small", `#${r.id} ${r.author}`));
  head.appendChild(likeBtn("replies", r.id, r.like_count, false));
  const replyTo = el("a", "small", "回复");
  replyTo.href = "#";
  replyTo.onclick = (e) => { e.preventDefault(); openComposer(r.id); };
  head.appendChild(replyTo);
  head.appendChild(el("span", "text-muted small ms-auto", r.created_at));
  box.appendChild(head);
  const body = el("div", "md mt-1");
  body.innerHTML = mdRender(r.content);
  box.appendChild(body);
  (r.children || []).forEach(c => box.appendChild(replyNode(c)));
  return box;
}

async function load() {
  const { ok, status, data } = await api("/threads/" + threadId);
  const tc = document.getElementById("thread");
  if (!ok) {
    tc.appendChild(el("div", "empty", status === 403 ? "论坛已关闭。" : "帖子不存在。"));
    document.getElementById("composer").style.display = "none";
    return;
  }
  const t = data.thread;
  const head = el("div", "d-flex align-items-start gap-3");
  const avatar = avatarTile(t.author);
  avatar.style.width = "52px";
  avatar.style.height = "52px";
  avatar.style.minWidth = "52px";
  avatar.style.fontSize = "20px";
  head.appendChild(avatar);
  const mid = el("div", "flex-grow-1");
  mid.appendChild(el("h3", "fw-bold mb-1", t.title));
  const meta = el("div", "text-muted small mb-2",
    `${t.author} · ${t.category_name} · ${t.created_at}`);
  mid.appendChild(meta);
  const content = el("div", "md");
  content.innerHTML = mdRender(t.content);
  mid.appendChild(content);
  head.appendChild(mid);
  const likeWrap = el("div", "mt-2");
  likeWrap.appendChild(likeBtn("threads", t.id, t.like_count, false));
  head.appendChild(likeWrap);
  tc.appendChild(head);

  const rc = document.getElementById("replies");
  rc.appendChild(el("h6", "fw-bold mb-2", `回复 (${data.replies.reduce((n, r) => n + 1 + (r.children || []).length, 0)})`));
  data.replies.forEach(r => rc.appendChild(replyNode(r)));
}

let currentParent = null;

function openComposer(parentReplyId) {
  currentParent = parentReplyId;
  const c = document.getElementById("composer");
  c.textContent = "";
  c.appendChild(el("h6", "fw-bold mb-2",
    parentReplyId ? `回复楼层 ${parentReplyId}(支持一层楼中楼)` : "发表回复"));
  const ta = el("textarea", "form-control");
  ta.maxLength = 2000;
  ta.id = "reply-content";
  ta.placeholder = "写下你的回复…";
  c.appendChild(ta);
  const row = el("div", "d-flex align-items-center gap-3 mt-3");
  const send = el("button", "btn-gs primary", "发送");
  send.onclick = submitReply;
  row.appendChild(send);
  if (parentReplyId) {
    const cancel = el("button", "btn-gs sm", "取消楼中楼");
    cancel.onclick = () => openComposer(null);
    row.appendChild(cancel);
  }
  row.appendChild(el("span", "text-muted small", loggedIn ? "" : "需要 GitHub 登录"));
  c.appendChild(row);
  ta.focus();
}

async function submitReply() {
  const content = document.getElementById("reply-content").value.trim();
  if (!content) return alert("内容不能为空");
  const body = { content };
  if (currentParent) body.parent_reply_id = currentParent;
  const r = await api(`/threads/${threadId}/replies`, { method: "POST", json: body });
  if (r.status === 401) return location.href = "/oauth/web/start?next=/thread/" + threadId;
  if (!r.ok) return alert(r.data && r.data.detail || "发送失败");
  location.reload();
}

topbar("/");
api("/me/session").then(({ data }) => {
  loggedIn = !!(data.user);
  openComposer(null);
});
load();
