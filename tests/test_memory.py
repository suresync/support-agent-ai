from app.db import get_connection, init_db
from app.memory import add_memory, search_similar


def test_search_similar_returns_related_memory(tmp_path, monkeypatch):
    # Use a deterministic stub embedding in tests to avoid downloading models
    from app import embeddings

    def fake_embed(texts, model_name=None):
        import numpy as np

        out = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            v[hash(t.lower().split()[0]) % 8] = 1.0
            out.append(v.tobytes())
        return out

    monkeypatch.setattr(embeddings, "embed_texts", fake_embed)

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
        question_summary="how to start tufting beginner kit",
        final_reply="The AK DUO starter kit is a good choice.",
        language="en",
        theme_tags=["beginner"],
        source="historic",
    )
    hits = search_similar(
        conn, "my package is missing three yarn cones", language="en", limit=2
    )
    assert hits[0].final_reply.startswith("We can reship")
