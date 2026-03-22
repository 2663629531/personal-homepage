from __future__ import annotations

import json
import html
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "diary" / "entries"
OUTPUT_FILE = ROOT / "diary" / "index.json"
POSTS_DIR = ROOT / "diary" / "posts"
COVERS_DIR = ROOT / "diary" / "covers"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")


@dataclass
class DiaryEntry:
    date: str
    displayDate: str
    tag: str
    title: str
    summary: str
    url: str
    coverImage: str | None = None


@dataclass
class DiaryDocument:
    entry: DiaryEntry
    body: str
    slug: str


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text

    _, raw_frontmatter, body = parts
    data: dict[str, str] = {}

    for line in raw_frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()

    return data, body.strip()


def first_paragraph(body: str) -> str:
    for block in body.split("\n\n"):
        text = block.strip()
        if not text or text.startswith("#"):
            continue
        return " ".join(text.splitlines()).strip()
    return ""


def resolve_cover_path(slug: str, frontmatter: dict[str, str]) -> str | None:
    explicit_cover = frontmatter.get("cover", "").strip()
    if explicit_cover:
        if explicit_cover.startswith(("http://", "https://", "./", "../")):
            return explicit_cover
        return f"./{explicit_cover.removeprefix('./')}"

    for extension in IMAGE_EXTENSIONS:
        candidate = COVERS_DIR / f"{slug}{extension}"
        if candidate.exists():
            return f"./diary/covers/{candidate.name}"

    return None


def render_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(
        r"\[(.+?)\]\((https?://.+?)\)",
        r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',
        escaped,
    )
    return escaped


def render_markdown(body: str) -> str:
    lines = body.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_tag: str | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph if part.strip())
            blocks.append(f"<p>{render_inline(text)}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_tag
        if list_items and list_tag:
            items = "".join(f"<li>{render_inline(item)}</li>" for item in list_items)
            blocks.append(f"<{list_tag}>{items}</{list_tag}>")
        list_items = []
        list_tag = None

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            flush_list()
            continue

        if line == "---":
            flush_paragraph()
            flush_list()
            blocks.append("<hr>")
            continue

        if line.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{render_inline(line[4:])}</h3>")
            continue

        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{render_inline(line[3:])}</h2>")
            continue

        if line.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h1>{render_inline(line[2:])}</h1>")
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        unordered_match = re.match(r"^[-*]\s+(.+)$", line)

        if ordered_match:
            flush_paragraph()
            if list_tag not in {None, "ol"}:
                flush_list()
            list_tag = "ol"
            list_items.append(ordered_match.group(1))
            continue

        if unordered_match:
            flush_paragraph()
            if list_tag not in {None, "ul"}:
                flush_list()
            list_tag = "ul"
            list_items.append(unordered_match.group(1))
            continue

        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def render_entry_page(
    entry: DiaryEntry,
    body: str,
    previous_entry: DiaryEntry | None = None,
    next_entry: DiaryEntry | None = None,
    latest_entry: DiaryEntry | None = None,
) -> str:
    content = render_markdown(body)
    previous_href = f"../../{previous_entry.url.removeprefix('./')}" if previous_entry else ""
    next_href = f"../../{next_entry.url.removeprefix('./')}" if next_entry else ""
    latest_href = f"../../{latest_entry.url.removeprefix('./')}" if latest_entry else ""
    cover_href = (
        entry.coverImage
        if entry.coverImage and entry.coverImage.startswith(("http://", "https://"))
        else f"../../{entry.coverImage.removeprefix('./')}"
        if entry.coverImage
        else ""
    )
    cover_block = (
        f"""
            <figure class="entry-cover">
              <img src="{cover_href}" alt="{html.escape(entry.title)} 封面图" loading="eager" />
            </figure>
        """
        if cover_href
        else ""
    )
    previous_link = (
        f"""
            <a class="entry-pager-card" href="{previous_href}">
              <span class="entry-pager-label">上一篇</span>
              <strong>{html.escape(previous_entry.title)}</strong>
              <time datetime="{previous_entry.date}">{previous_entry.displayDate}</time>
            </a>
        """
        if previous_entry
        else ""
    )
    next_link = (
        f"""
            <a class="entry-pager-card" href="{next_href}">
              <span class="entry-pager-label">下一篇</span>
              <strong>{html.escape(next_entry.title)}</strong>
              <time datetime="{next_entry.date}">{next_entry.displayDate}</time>
            </a>
        """
        if next_entry
        else ""
    )
    pager = (
        f"""
          <nav class="entry-pager" aria-label="日记翻页">
{previous_link}
{next_link}
          </nav>
        """
        if previous_link or next_link
        else ""
    )
    latest_panel = ""
    if latest_entry:
        if latest_entry.url == entry.url:
            latest_panel = """
          <section class="entry-latest" aria-label="最新日记">
            <span class="entry-latest-label">最新一篇</span>
            <p>你正在读的这篇，就是目前最新更新。</p>
          </section>
            """
        else:
            latest_panel = f"""
          <section class="entry-latest" aria-label="最新日记">
            <span class="entry-latest-label">最新一篇</span>
            <a href="{latest_href}">{html.escape(latest_entry.title)}</a>
            <p>{html.escape(latest_entry.summary)}</p>
          </section>
            """
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(entry.title)} | 副驾驶手记</title>
    <meta name="description" content="{html.escape(entry.summary)}" />
    <link
      rel="icon"
      href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%23111115'/%3E%3Ctext x='50%25' y='54%25' dominant-baseline='middle' text-anchor='middle' font-size='34' fill='white' font-family='Arial'%3EX%3C/text%3E%3C/svg%3E"
    />
    <link rel="stylesheet" href="../../styles.css" />
  </head>
  <body>
    <div class="reading-progress" aria-hidden="true">
      <div class="reading-progress-bar" data-reading-progress></div>
    </div>
    <div class="site-shell">
      <header class="topbar">
        <div class="topbar-inner">
          <a class="brand" href="../../index.html#home">副驾驶手记</a>
          <nav class="nav" aria-label="主导航">
            <div class="nav-links">
              <a href="../../index.html#writing">博客</a>
              <a href="../../index.html#diary">日记</a>
              <a href="../../index.html#skills">项目</a>
              <a href="../../index.html#about">关于我</a>
            </div>
            <div class="nav-actions">
              <button class="theme-toggle" type="button" aria-label="切换主题">
                <span class="theme-toggle-icon" aria-hidden="true"></span>
                <span class="theme-toggle-text">Toggle theme</span>
              </button>
            </div>
          </nav>
        </div>
      </header>

      <main>
        <div class="entry-shell">
          <div class="entry-actions">
            <a href="../../index.html#home">返回首页</a>
            <a href="../../index.html#diary">返回日记列表</a>
          </div>
          <article class="entry-article reveal is-visible">
{cover_block}
            <div class="entry-meta">
              <time datetime="{entry.date}">{entry.displayDate}</time>
              <span>{html.escape(entry.tag)}</span>
            </div>
            <h1>{html.escape(entry.title)}</h1>
            <p class="entry-summary">{html.escape(entry.summary)}</p>
            <div class="entry-content">
{content}
            </div>
          </article>
{pager}
{latest_panel}
        </div>
      </main>

      <footer class="footer">
        <div class="footer-inner">
          <div class="footer-brand">
            <h2>副驾驶手记</h2>
            <p>© 2026 副驾驶手记 · All rights reserved</p>
            <div class="status-pill">All Systems Normal</div>
          </div>
        </div>
      </footer>
    </div>

    <script src="../../script.js?v=20260322-diary-cover"></script>
  </body>
</html>
"""


def build_entry(path: Path) -> DiaryDocument | None:
    text = path.read_text(encoding="utf-8").strip()
    frontmatter, body = parse_frontmatter(text)

    date = frontmatter.get("date", path.stem)
    title = frontmatter.get("title", path.stem)
    tag = frontmatter.get("tag", "Diary")
    summary = frontmatter.get("summary", "") or first_paragraph(body)
    cover_image = resolve_cover_path(path.stem, frontmatter)

    if not date or not title or not summary:
        return None

    display_date = date.replace("-", ".")
    url = f"./diary/posts/{path.stem}.html"

    return DiaryDocument(
        entry=DiaryEntry(
            date=date,
            displayDate=display_date,
            tag=tag,
            title=title,
            summary=summary,
            url=url,
            coverImage=cover_image,
        ),
        body=body,
        slug=path.stem,
    )


def main() -> None:
    documents: list[DiaryDocument] = []

    for path in sorted(ENTRIES_DIR.glob("*.md"), reverse=True):
        document = build_entry(path)
        if document:
            documents.append(document)

    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    latest_entry = documents[0].entry if documents else None

    for index, document in enumerate(documents):
        previous_entry = documents[index - 1].entry if index > 0 else None
        next_entry = documents[index + 1].entry if index + 1 < len(documents) else None
        output_path = POSTS_DIR / f"{document.slug}.html"
        output_path.write_text(
            render_entry_page(
                document.entry,
                document.body,
                previous_entry=previous_entry,
                next_entry=next_entry,
                latest_entry=latest_entry,
            ),
            encoding="utf-8",
        )

    payload = [document.entry.__dict__ for document in documents]
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
