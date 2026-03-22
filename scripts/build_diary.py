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

    def normalize_value(value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {"'", '"'}:
            return trimmed[1:-1].strip()
        return trimmed

    for line in raw_frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = normalize_value(value)

    return data, body.strip()


def first_paragraph(body: str) -> str:
    for block in body.split("\n\n"):
        text = block.strip()
        if not text or text.startswith("#"):
            continue
        return " ".join(text.splitlines()).strip()
    return ""


def plain_text_excerpt(text: str) -> str:
    value = text.strip()
    value = re.sub(r"\[(.+?)\]\((https?://.+?)\)", r"\1", value)
    value = re.sub(r"^>\s*\[![^\]]+\]\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^>\s*", "", value, flags=re.MULTILINE)
    value = value.replace(">", " ")
    value = re.sub(r"^[-*]\s+\[[ xX]\]\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^[-*]\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\d+\.\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"[#*_`=]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def relative_site_path(path: Path) -> str | None:
    try:
        relative_path = path.relative_to(ROOT)
    except ValueError:
        return None
    return f"./{relative_path.as_posix()}"


def resolve_cover_path(path: Path, frontmatter: dict[str, str]) -> str | None:
    explicit_cover = frontmatter.get("cover", "").strip()
    if explicit_cover:
        if explicit_cover.startswith(("http://", "https://")):
            return explicit_cover

        explicit_path = (path.parent / explicit_cover).resolve()
        normalized_explicit_path = relative_site_path(explicit_path)
        if normalized_explicit_path:
            return normalized_explicit_path

        fallback_path = (ROOT / explicit_cover.removeprefix("./")).resolve()
        normalized_fallback_path = relative_site_path(fallback_path)
        if normalized_fallback_path:
            return normalized_fallback_path

    for extension in IMAGE_EXTENSIONS:
        candidate = COVERS_DIR / f"{path.stem}{extension}"
        if candidate.exists():
            normalized_candidate = relative_site_path(candidate)
            if normalized_candidate:
                return normalized_candidate

    return None


def resolve_tag(frontmatter: dict[str, str]) -> str:
    direct_tag = frontmatter.get("tag", "").strip()
    if direct_tag:
        return direct_tag

    raw_tags = frontmatter.get("tags", "").strip()
    if raw_tags.startswith("[") and raw_tags.endswith("]"):
        items = [
            item.strip().strip("'\"")
            for item in raw_tags[1:-1].split(",")
            if item.strip()
        ]
        if items:
            return " / ".join(items[:3])

    if raw_tags:
        return raw_tags

    return "Diary"


def render_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"==(.+?)==", r"<mark>\1</mark>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(
        r"\[(.+?)\]\((https?://.+?)\)",
        r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',
        escaped,
    )
    return escaped


def strip_quote_prefix(line: str) -> str:
    stripped = line.lstrip()
    if not stripped.startswith(">"):
        return line
    stripped = stripped[1:]
    if stripped.startswith(" "):
        stripped = stripped[1:]
    return stripped


def callout_class(callout_type: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", callout_type.lower()).strip("-")
    return normalized or "note"


def default_callout_title(callout_type: str) -> str:
    normalized = callout_type.replace("-", " ").replace("_", " ").strip()
    return normalized.title() if normalized else "Note"


def render_markdown(body: str) -> str:
    lines = body.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[tuple[str, bool | None]] = []
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
            rendered_items: list[str] = []
            for item_text, checked in list_items:
                if checked is None:
                    rendered_items.append(f"<li>{render_inline(item_text)}</li>")
                    continue

                checked_attr = " checked" if checked else ""
                rendered_items.append(
                    "<li class=\"task-list-item\">"
                    f"<label class=\"task-item\"><input type=\"checkbox\" disabled{checked_attr}>"
                    f"<span>{render_inline(item_text)}</span></label></li>"
                )
            items = "".join(rendered_items)
            blocks.append(f"<{list_tag}>{items}</{list_tag}>")
        list_items = []
        list_tag = None

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            flush_list()
            index += 1
            continue

        if line.startswith(">"):
            flush_paragraph()
            flush_list()

            quote_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                quote_lines.append(lines[index])
                index += 1

            first_quote_line = quote_lines[0].lstrip()
            callout_match = re.match(r"^>\s*\[!([^\]]+)\][+-]?\s*(.*)$", first_quote_line)

            if callout_match:
                raw_callout_type = callout_match.group(1).strip()
                callout_title = callout_match.group(2).strip()
                inner_markdown = "\n".join(strip_quote_prefix(item) for item in quote_lines[1:]).strip()
                inner_html = render_markdown(inner_markdown) if inner_markdown else ""
                callout_type_class = callout_class(raw_callout_type)

                if callout_type_class == "quote" and callout_title and not inner_html:
                    inner_html = f"<p>{render_inline(callout_title)}</p>"
                    callout_title = ""

                title_html = (
                    f"<div class=\"callout-title\">{render_inline(callout_title or default_callout_title(raw_callout_type))}</div>"
                    if callout_type_class != "quote" or callout_title
                    else ""
                )

                blocks.append(
                    f"<section class=\"callout callout-{callout_type_class}\">"
                    f"{title_html}<div class=\"callout-content\">{inner_html}</div></section>"
                )
                continue

            inner_markdown = "\n".join(strip_quote_prefix(item) for item in quote_lines).strip()
            inner_html = render_markdown(inner_markdown) if inner_markdown else ""
            blocks.append(f"<blockquote>{inner_html}</blockquote>")
            continue

        if line == "---":
            flush_paragraph()
            flush_list()
            blocks.append("<hr>")
            index += 1
            continue

        if line.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{render_inline(line[4:])}</h3>")
            index += 1
            continue

        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{render_inline(line[3:])}</h2>")
            index += 1
            continue

        if line.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h1>{render_inline(line[2:])}</h1>")
            index += 1
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        task_match = re.match(r"^[-*]\s+\[([ xX])\]\s+(.+)$", line)
        unordered_match = re.match(r"^[-*]\s+(.+)$", line)

        if ordered_match:
            flush_paragraph()
            if list_tag not in {None, "ol"}:
                flush_list()
            list_tag = "ol"
            list_items.append((ordered_match.group(1), None))
            index += 1
            continue

        if task_match:
            flush_paragraph()
            if list_tag not in {None, "ul"}:
                flush_list()
            list_tag = "ul"
            list_items.append((task_match.group(2), task_match.group(1).lower() == "x"))
            index += 1
            continue

        if unordered_match:
            flush_paragraph()
            if list_tag not in {None, "ul"}:
                flush_list()
            list_tag = "ul"
            list_items.append((unordered_match.group(1), None))
            index += 1
            continue

        flush_list()
        paragraph.append(line)
        index += 1

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
    tag = resolve_tag(frontmatter)
    summary = plain_text_excerpt(frontmatter.get("summary", "") or first_paragraph(body))
    cover_image = resolve_cover_path(path, frontmatter)

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
