from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "diary" / "entries"
OUTPUT_FILE = ROOT / "diary" / "index.json"


@dataclass
class DiaryEntry:
    date: str
    displayDate: str
    tag: str
    title: str
    summary: str


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


def build_entry(path: Path) -> DiaryEntry | None:
    text = path.read_text(encoding="utf-8").strip()
    frontmatter, body = parse_frontmatter(text)

    date = frontmatter.get("date", path.stem)
    title = frontmatter.get("title", path.stem)
    tag = frontmatter.get("tag", "Diary")
    summary = frontmatter.get("summary", "") or first_paragraph(body)

    if not date or not title or not summary:
        return None

    display_date = date.replace("-", ".")
    return DiaryEntry(
        date=date,
        displayDate=display_date,
        tag=tag,
        title=title,
        summary=summary,
    )


def main() -> None:
    entries: list[DiaryEntry] = []

    for path in sorted(ENTRIES_DIR.glob("*.md"), reverse=True):
        entry = build_entry(path)
        if entry:
            entries.append(entry)

    payload = [entry.__dict__ for entry in entries]
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
