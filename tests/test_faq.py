from pathlib import Path

from app.faq import load_faq_chunks

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_faq_chunks_returns_non_empty_chunks_from_repo():
    chunks = load_faq_chunks(REPO_ROOT)
    assert len(chunks) > 0
    assert all(isinstance(chunk, str) and chunk.strip() for chunk in chunks)
    combined = "\n".join(chunks)
    assert "Shipping" in combined or "shipping" in combined
    assert "tufting" in combined.lower()
