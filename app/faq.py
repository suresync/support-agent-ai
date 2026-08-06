from __future__ import annotations

import re
from pathlib import Path

FAQ_FILES = ("FAQ.md", "BEGINNER-QA.md", "TUFTINGSHOP_FAQ.md")
_HEADING_PATTERN = re.compile(r"^#{2,3}\s")


def _split_on_headings(text: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    for line in text.splitlines(keepends=True):
        if _HEADING_PATTERN.match(line):
            if current:
                chunk = "".join(current).strip()
                if chunk:
                    chunks.append(chunk)
            current = [line]
        else:
            current.append(line)

    if current:
        chunk = "".join(current).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def load_faq_chunks(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    chunks: list[str] = []

    for name in FAQ_FILES:
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        chunks.extend(_split_on_headings(text))

    return chunks
