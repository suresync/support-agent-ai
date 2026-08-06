from app.db import get_connection, init_db
from app.memory import add_memory, search_similar


def _fake_embed_bow(texts, model_name=None):
    """Bag-of-words stub so overlapping tokens produce higher cosine scores."""
    import hashlib

    import numpy as np

    dims = 256
    out = []
    for t in texts:
        v = np.zeros(dims, dtype=np.float32)
        for word in t.lower().split():
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % dims
            v[idx] += 1.0
        out.append(v.tobytes())
    return out


def test_search_similar_returns_related_memory(tmp_path, monkeypatch):
    # Use a deterministic stub embedding in tests to avoid downloading models
    from app import embeddings

    monkeypatch.setattr(embeddings, "embed_texts", _fake_embed_bow)

    path = str(tmp_path / "t.db")
    init_db(path)
    conn = get_connection(path)
    add_memory(
        conn,
        question_summary="package missing yarn cones order shipment",
        final_reply="We can reship or refund the missing cones.",
        language="en",
        theme_tags=["missing-items"],
        source="historic",
    )
    add_memory(
        conn,
        question_summary="beginner tufting starter gun recommendations",
        final_reply="The AK DUO starter kit is a good choice.",
        language="en",
        theme_tags=["beginner"],
        source="historic",
    )
    hits = search_similar(
        conn, "my package is missing three yarn cones", language="en", limit=2
    )
    assert len(hits) == 2
    assert hits[0].score > hits[1].score
    assert hits[0].final_reply.startswith("We can reship")


def test_search_similar_filters_by_language(tmp_path, monkeypatch):
    from app import embeddings

    monkeypatch.setattr(embeddings, "embed_texts", _fake_embed_bow)

    path = str(tmp_path / "t.db")
    init_db(path)
    conn = get_connection(path)
    add_memory(
        conn,
        question_summary="missing yarn cones from order",
        final_reply="We can reship or refund the missing cones.",
        language="en",
        theme_tags=["missing-items"],
        source="historic",
    )
    add_memory(
        conn,
        question_summary="ontbrekende garen cones bestelling",
        final_reply="We kunnen de ontbrekende cones opnieuw versturen.",
        language="nl",
        theme_tags=["missing-items"],
        source="historic",
    )
    hits = search_similar(conn, "missing yarn cones", language="en", limit=5)
    assert len(hits) == 1
    assert hits[0].final_reply.startswith("We can reship")
