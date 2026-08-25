AUTHOR_EXPR = "COALESCE(a.name || '(@' || u.login || ')', '@' || u.login)"


def thread_line(t: dict) -> str:
    return (
        f"[{t['id']}] {t['title']}\n"
        f"  作者: {t['author']} | 分类: {t['category']}"
        f" | 赞:{t['like_count']} 回复:{t['reply_count']} | {t['created_at']}"
    )


def threads_text(rows: list[dict]) -> str:
    if not rows:
        return "(暂无帖子)"
    return "\n".join(thread_line(r) for r in rows)


def reply_block(r: dict, indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines = [
        f"{pad}[回复{r['id']}] {r['author']} | 赞:{r['like_count']}"
        f" | {r['created_at']}",
        f"{pad}{r['content']}",
    ]
    for child in r.get("children", []):
        lines += reply_block(child, indent + 1)
    return lines


def thread_detail_text(thread: dict, replies: list[dict]) -> str:
    head = [
        f"# [{thread['id']}] {thread['title']}",
        (
            f"作者: {thread['author']} | 分类: {thread['category']}"
            f" | 赞:{thread['like_count']} | {thread['created_at']}"
        ),
        "",
        thread["content"],
        "",
    ]
    body: list[str] = []
    for r in replies:
        body += reply_block(r) + [""]
    if not body:
        body = ["(暂无回复)"]
    return "\n".join(head + body)


def modules_text(rows: list[dict]) -> str:
    if not rows:
        return "(暂无模块)"
    lines = []
    for m in rows:
        lines.append(
            f"[{m['slug']}] v{m['latest_version']} by @{m['owner_login']}\n"
            f"  {m['description']}\n"
            f"  下载:{m['download_count']}"
        )
    return "\n".join(lines)
