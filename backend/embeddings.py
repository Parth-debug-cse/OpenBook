from __future__ import annotations
from typing import List
from fastembed import TextEmbedding
from backend.config import EMBED_MODEL

_model: TextEmbedding | None = None

_DOC_PREFIX   = "search_document: "
_QUERY_PREFIX = "search_query: "


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=EMBED_MODEL, max_length=512)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = _get_model()
    prefixed = [_DOC_PREFIX + t for t in texts]
    vectors = list(model.embed(prefixed))
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> List[float]:
    model = _get_model()
    vectors = list(model.embed([_QUERY_PREFIX + query]))
    return vectors[0].tolist()
