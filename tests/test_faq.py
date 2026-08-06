from pathlib import Path

from app.faq import _split_on_headings, load_faq_chunks

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_faq_chunks_returns_non_empty_chunks_from_repo():
    chunks = load_faq_chunks(REPO_ROOT)
    assert len(chunks) > 3
    assert all(isinstance(chunk, str) and chunk.strip() for chunk in chunks)
    assert any(chunk.lstrip().startswith(("##", "###")) for chunk in chunks)
    combined = "\n".join(chunks)
    assert "Shipping" in combined or "shipping" in combined
    assert "tufting" in combined.lower()


def test_split_on_headings_splits_at_markdown_headings():
    markdown = """# Title

Intro before first heading.

## Section One
Content for section one.

### Subsection A
Details here.

## Section Two
Content for section two.
"""
    chunks = _split_on_headings(markdown)
    assert len(chunks) == 4
    assert chunks[0].startswith("# Title")
    assert chunks[1].startswith("## Section One")
    assert chunks[2].startswith("### Subsection A")
    assert chunks[3].startswith("## Section Two")
