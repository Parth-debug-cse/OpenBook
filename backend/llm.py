from __future__ import annotations
import time
import logging
from typing import List, Dict, Any, Generator
from llama_cpp import Llama
from backend.config import (
    LLM_MODEL_PATH, LLM_N_CTX, LLM_N_THREADS, LLM_N_BATCH,
    LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_REPEAT_PENALTY, LLM_TOP_K, LLM_TOP_P,
    TOP_K_RETRIEVAL,
)
from backend.embeddings import embed_query
from backend.vectordb import search

logger = logging.getLogger(__name__)

_llm: Llama | None = None

SYSTEM_PROMPT = (
    "You are OpenBook, a study assistant. "
    "Answer questions using ONLY the provided context excerpts. "
    "If the context does not contain the answer, say: 'I don't have enough information in the uploaded notes to answer this.' "
    "Be concise. Do not make up facts."
)


def _get_llm() -> Llama:
    global _llm
    if _llm is None:
        if not LLM_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"LLM model not found at {LLM_MODEL_PATH}. "
                "Download lfm-1.2b-q4_k_m.gguf and place it in the models/ directory."
            )
        logger.info("Loading LLM from %s …", LLM_MODEL_PATH)
        _llm = Llama(
            model_path   = str(LLM_MODEL_PATH),
            n_ctx        = LLM_N_CTX,
            n_threads    = LLM_N_THREADS,
            n_batch      = LLM_N_BATCH,
            verbose      = False,
            use_mmap     = True,
            n_gpu_layers = 0,
        )
        logger.info("LLM loaded.")
    return _llm


def _build_prompt(query: str, context_chunks: List[str]) -> str:
    ctx_block = "\n\n---\n\n".join(
        f"[Excerpt {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    prompt = (
        f"### System\n{SYSTEM_PROMPT}\n\n"
        f"### Context\n{ctx_block}\n\n"
        f"### Question\n{query}\n\n"
        f"### Answer\n"
    )
    
    # Rough estimate: average English word ≈ 1.3 tokens, we want 80% safety margin
    max_chars = int(LLM_N_CTX * 0.8 * 4)  # ~4 chars per token as conservative estimate
    if len(prompt) > max_chars:
        logger.warning(
            "Prompt (%d chars) exceeds context window (%d tokens). Truncating context.",
            len(prompt), LLM_N_CTX,
        )
        # Remove chunks from the end until it fits
        prompt = (
            f"### System\n{SYSTEM_PROMPT}\n\n"
            f"### Context\n"
        )
        remaining = max_chars - len(prompt) - 100  # Reserve space for question+answer
        for i, chunk in enumerate(context_chunks):
            chunk_text = f"[Excerpt {i+1}]\n{chunk}"
            if len(chunk_text) + 7 > remaining:  # 7 for "\n\n---\n\n"
                logger.debug("Dropped context chunk %d due to size constraints", i)
                break
            prompt += chunk_text + "\n\n---\n\n"
            remaining -= len(chunk_text) + 7
        prompt += f"### Question\n{query}\n\n### Answer\n"
    
    return prompt




def stream_rag(query: str, top_k: int = TOP_K_RETRIEVAL) -> Generator[str, None, None]:
    import json

    try:
        qvec    = embed_query(query)
        results = search(qvec, top_k=top_k)

        if not results:
            yield f"data: {json.dumps({'type': 'error', 'text': 'No documents ingested yet. Please upload study materials first.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        context_chunks = [r["text"] for r in results]
        sources        = [
            {
                "source": r["source"],
                "page": r.get("page", 0),
                "text": r["text"][:300],
                "distance": round(r.get("_distance", 0.0), 4),
            }
            for r in results
        ]

        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        prompt = _build_prompt(query, context_chunks)
        llm    = _get_llm()

        stop_tokens = ["### Question", "### Context", "### System"]

        for chunk in llm(
            prompt,
            max_tokens     = LLM_MAX_TOKENS,
            temperature    = LLM_TEMPERATURE,
            repeat_penalty = LLM_REPEAT_PENALTY,
            top_k          = LLM_TOP_K,
            top_p          = LLM_TOP_P,
            stop           = stop_tokens,
            echo           = False,
            stream         = True,
        ):
            token_text = chunk["choices"][0]["text"]
            if token_text:
                yield f"data: {json.dumps({'type': 'token', 'text': token_text})}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
