from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .llm import answer_workspace_question
from .local_llm import LocalLLM
from .rag import Passage, WorkspaceIndex


load_dotenv()


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8_000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=8)


class AppState:
    index: WorkspaceIndex | None = None
    client: LocalLLM | None = None
    indexed_at: float | None = None
    chunk_count: int = 0
    lock = asyncio.Lock()


state = AppState()


def _settings() -> tuple[Path, str, str]:
    workspace = Path(os.getenv("PLANNING_WORKSPACE", "documents")).resolve(strict=True)
    llm_url = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.getenv("LOCAL_LLM_MODEL", "kimi")
    return workspace, llm_url, model


async def _build_index() -> None:
    workspace, _, _ = _settings()
    new_index = WorkspaceIndex(workspace)
    count = await asyncio.to_thread(new_index.build)
    state.index = new_index
    state.chunk_count = count
    state.indexed_at = time.time()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _, llm_url, model = _settings()
    state.client = LocalLLM(llm_url, model)
    await _build_index()
    yield


app = FastAPI(title="Private Planning Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])


@app.get("/api/status")
async def status() -> dict[str, object]:
    workspace, _, model = _settings()
    return {
        "ready": state.index is not None and state.client is not None,
        "model": model,
        "workspace": workspace.name,
        "chunks": state.chunk_count,
        "indexed_at": state.indexed_at,
        "skipped": len(state.index.skipped) if state.index else 0,
        "privacy": "loopback-only",
    }


@app.post("/api/reindex")
async def reindex() -> dict[str, object]:
    if state.lock.locked():
        raise HTTPException(409, "Indexing is already in progress")
    async with state.lock:
        started = time.perf_counter()
        await _build_index()
    return {"chunks": state.chunk_count, "elapsed_seconds": round(time.perf_counter() - started, 3)}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    if state.index is None or state.client is None:
        raise HTTPException(503, "Assistant is still starting")
    return StreamingResponse(_event_stream(request), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    })


async def _event_stream(request: ChatRequest) -> AsyncIterator[str]:
    started = time.perf_counter()
    yield _sse("status", {"stage": "searching", "message": "Searching local files"})
    passages = await asyncio.to_thread(state.index.search, request.question, 5, 0.04)  # type: ignore[union-attr]
    yield _sse("sources", {"items": [_source(p) for p in passages]})
    yield _sse("status", {"stage": "thinking", "message": "Kimi is preparing the answer"})
    task = asyncio.create_task(asyncio.to_thread(
        answer_workspace_question,
        state.client,
        request.question,
        passages,
        [item.model_dump() for item in request.history],
    ))
    try:
        while not task.done():
            elapsed = time.perf_counter() - started
            timeout = 1.0 if elapsed >= 9.0 else min(9.0 - elapsed, 1.0)
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=max(timeout, 0.1))
            except TimeoutError:
                if elapsed >= 9.0:
                    yield _sse("progress", {"elapsed_seconds": int(time.perf_counter() - started)})
        answer = await task
        elapsed = time.perf_counter() - started
        yield _sse("complete", {
            "answer": answer,
            "elapsed_seconds": round(elapsed, 2),
            "show_timing": elapsed >= 10.0,
            "sources": [_source(p) for p in passages],
        })
    except Exception as error:
        yield _sse("error", {"message": str(error), "elapsed_seconds": round(time.perf_counter() - started, 2)})


def _source(passage: Passage) -> dict[str, object]:
    return {"document": passage.document, "location": passage.location, "score": round(passage.score, 3)}


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


frontend = Path(__file__).resolve().parents[1] / "web" / "dist"
if frontend.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = (frontend / path).resolve()
        if path and candidate.is_relative_to(frontend) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend / "index.html")
