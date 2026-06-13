from fastapi import APIRouter, HTTPException
from backend.vectordb import get_all_docs, delete_doc, get_db_status

router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.get("")
async def list_docs():
    return {"docs": get_all_docs(), **get_db_status()}


@router.delete("/{doc_id}")
async def delete_doc_endpoint(doc_id: str):
    try:
        deleted = delete_doc(doc_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if deleted == 0:
        raise HTTPException(404, f"No document found with id: {doc_id}")
    return {"status": "ok", "chunks_deleted": deleted}
