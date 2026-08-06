from __future__ import annotations

_model = None
_model_name: str | None = None


def embed_texts(texts: list[str], model_name: str | None = None) -> list[bytes]:
    global _model, _model_name

    import numpy as np
    from sentence_transformers import SentenceTransformer

    from app.config import get_settings

    if model_name is None:
        model_name = get_settings().embedding_model_name

    if _model is None or _model_name != model_name:
        _model = SentenceTransformer(model_name)
        _model_name = model_name

    vectors = _model.encode(texts, convert_to_numpy=True)
    return [vector.astype(np.float32).tobytes() for vector in vectors]
