from __future__ import annotations
import logging
import re
import uuid
from typing import List, Dict, Any
import lancedb
import pyarrow as pa
from backend.config import LANCEDB_DIR, LANCEDB_TABLE, EMBED_DIM, TOP_K_RETRIEVAL, LANCEDB_RESET_ON_DIM_CHANGE

logger = logging.getLogger(__name__)

DOC_ID_RE = re.compile(r"^[a-f0-9]{32}$")
SCHEMA = pa.schema([
    pa.field("id", pa.utf8()),
    pa.field("doc_id", pa.utf8()),
    pa.field("source", pa.utf8()),
    pa.field("page", pa.int32()),
    pa.field("chunk_idx", pa.int32()),
    pa.field("text", pa.utf8()),
    pa.field("vector", pa.list_(pa.float32(), EMBED_DIM)),
])

_db: lancedb.DBConnection | None = None
_table: lancedb.table.Table | None = None
_last_dimension_reset: str | None = None


def _list_table_names(db: lancedb.DBConnection) -> list[str]:
    existing = db.list_tables()
    if hasattr(existing, "tables"):
        return list(existing.tables)
    return list(existing)


def _reset_table(db: lancedb.DBConnection) -> lancedb.table.Table:
    global _last_dimension_reset
    db.drop_table(LANCEDB_TABLE)
    created = db.create_table(LANCEDB_TABLE, schema=SCHEMA)
    _last_dimension_reset = (
        f"Embedding dimension changed to {EMBED_DIM}; vector DB was reset. "
        "Re-ingest your notes."
    )
    return created


def _get_table() -> lancedb.table.Table:
    global _db, _table
    if _db is None:
        _db = lancedb.connect(str(LANCEDB_DIR))
    if _table is None:
        table_names = _list_table_names(_db)
        if LANCEDB_TABLE in table_names:
            table = _db.open_table(LANCEDB_TABLE)
            stored_dim = table.schema.field("vector").type.list_size
            if stored_dim != EMBED_DIM:
                if not LANCEDB_RESET_ON_DIM_CHANGE:
                    raise ValueError(
                        f"Embedding dimension changed ({stored_dim} -> {EMBED_DIM}). "
                        "Delete data/lancedb or set LANCEDB_RESET_ON_DIM_CHANGE=true."
                    )
                logger.warning(
                    "Embedding dimension changed (%d -> %d). Resetting vector DB.",
                    stored_dim, EMBED_DIM,
                )
                _table = _reset_table(_db)
            else:
                _table = table
        else:
            _table = _db.create_table(LANCEDB_TABLE, schema=SCHEMA)
    return _table


def validate_doc_id(doc_id: str) -> None:
    if not DOC_ID_RE.fullmatch(doc_id):
        raise ValueError("Invalid document id.")


def add_chunks(chunks: List[Dict[str, Any]]) -> None:
    table = _get_table()
    for c in chunks:
        if "id" not in c:
            c["id"] = str(uuid.uuid4())
    table.add(chunks)


def doc_exists(doc_id: str) -> bool:
    validate_doc_id(doc_id)
    table = _get_table()
    if table.count_rows() == 0:
        return False
    try:
        arrow = table.to_arrow()
        return doc_id in arrow.column("doc_id").to_pylist()
    except Exception:
        logger.exception("doc_exists filter failed")
        return False


def search(query_vector: List[float], top_k: int = TOP_K_RETRIEVAL) -> List[Dict]:
    table = _get_table()
    results = (
        table.search(query_vector)
             .metric("cosine")
             .limit(top_k)
             .to_list()
    )
    return results


def get_all_docs() -> List[Dict[str, str]]:
    table = _get_table()
    arrow = table.to_arrow()
    doc_ids = arrow.column("doc_id").to_pylist()
    sources = arrow.column("source").to_pylist()
    seen = set()
    rows = []
    for doc_id, source in zip(doc_ids, sources):
        if doc_id not in seen:
            seen.add(doc_id)
            rows.append({"doc_id": doc_id, "source": source})
    return rows


def get_db_status() -> Dict[str, Any]:
    table = _get_table()
    return {
        "vector_dim": EMBED_DIM,
        "row_count": table.count_rows(),
        "warning": _last_dimension_reset,
    }


def delete_doc(doc_id: str) -> int:
    validate_doc_id(doc_id)
    table = _get_table()
    before = table.count_rows()
    table.delete(f"doc_id = '{doc_id}'")
    after = table.count_rows()
    return before - after
