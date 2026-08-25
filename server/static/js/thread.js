/* 帖子详情:正文、楼中楼回复、点赞、回帖 */

const threadId = Number(location.pathname.split("/").pop());
let loggedIn = false;

function likeBtn(targetType, targetId, count) {
  const btn = el("span", "like-btn", `赞 ${count}`);
  btn.onclick = async () => {
    const r = await api(`/${targetType}/${targetId}/like`, { method: "POST" });
    if (r.status === 401) return location.href = "/oauth/web/start?next=/thread/" + threadId;
    if (!r.ok) return alert(r.data && r.data.detail || "操作失败");
    btn.textContent = `赞 ${r.data.likes}` + (r.data.liked ? " · 已赞" : "");
  };
  return btn;
}

function replyNode(r) {
  const box = el("div", "reply");
  const head = el("div", "row");
  head.appendChild(el("span", null, `[${r.id}] ${r.author}`));
  head.appendChild(likeBtn("replies", r.id, r.like_count));
  const replyTo = el("a", null, " 回复");
  replyTo.href = "#";
  replyTo.onclick = (e) => { e.preventDefault(); openComposer(r.id); };
  head.appendChild(replyTo);
  head.appendChild(el("span", "muted right", r.created_at));
  box.appendChild(head);
  box.appendChild(el("div", null, r.content));
  (r.children || []).forEach(c => box.appendChild(replyNode(Object.assign(c, { cls: true }))));
  return box;
}

async function load() {
  const { ok, status, data } = await api("/threads/" + threadId);
  const tc = document.getElementById("thread");
  if (!ok) {
    tc.appendChild(el("div", "muted", status === 403 ? "论坛已关闭。" : "帖子不存在。"));
    document.getElementById("composer").style.display = "none";
    return;
  }
  const t = data.thread;
  const head = el("div", "row");
  head.appendChild(el("h2", null, t.title));
  head.appendChild(likeBtn("threads", t.id, t.like_count));
  tc.appendChild(head);
  tc.appendChild(el("div", "muted", `${t.author} · ${t.category_name} · ${t.created_at}`));
  tc.appendChild(el("p", null, t.content));

  const rc = document.getElementById("replies");
  rc.appendChild(el("h3", null, `回复 (${data.replies.reduce((n, r) => n + 1 + (r.children || []).length, 0)})`));
  data.replies.forEach(r => rc.appendChild(replyNode(r)));
}

let currentParent = null;

function openComposer(parentReplyId) {
  currentParent = parentReplyId;
  const c = document.getElementById("composer");
  c.textContent = "";
  c.appendChild(el("h3", null,
    parentReplyId ? `回复楼层 ${parentReplyId}(支持一层楼中楼)` : "发表回复"));
  const ta = el("textarea");
  ta.maxLength = 2000;
  ta.id = "reply-content";
  c.appendChild(ta);
  const row = el("div", "row");
  row.style.marginTop = "10px";
  const send = el("button", "btn primary", "发送");
  send.onclick = submitReply;
  row.appendChild(send);
  if (parentReplyId) {
    const cancel = el("button", "btn small", "取消楼中楼");
    cancel.onclick = () => openComposer(null);
    row.appendChild(cancel);
  }
  row.appendChild(el("span", "muted", loggedIn ? "" : "需要 GitHub 登录"));
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

topbar("/thread");
api("/me/session").then(({ data }) => {
  loggedIn = !!(data.user);
  openComposer(null);
});
load();
