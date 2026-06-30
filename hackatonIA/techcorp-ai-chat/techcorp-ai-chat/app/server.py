"""
server.py — TechCorp secure financial assistant.

A thin, auditable gateway between the browser UI and the Ollama inference
server. Every user message passes through the security layer before it can
reach the model, so the inherited backdoor cannot be activated through this
front door even if a poisoned model were ever loaded.

Run:
    uvicorn app.server:app --reload --port 8500
Then open http://localhost:8500
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.security import BLOCK_MESSAGE, Severity, inspect

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MODEL", "phi35-financial-clean")
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="TechCorp Financial Assistant", version="1.0.0")

# In-memory audit trail of blocked/flagged events (resets on restart).
SECURITY_LOG: list[dict] = []


class ChatRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"assistant"|"system", content: str}]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> JSONResponse:
    """Report whether the inference server is reachable and which model is live."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
        return JSONResponse(
            {
                "connected": True,
                "model": MODEL,
                "model_available": any(MODEL in m for m in models),
                "available_models": models,
            }
        )
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the UI
        return JSONResponse({"connected": False, "model": MODEL, "error": str(exc)})


@app.get("/api/security-log")
def security_log() -> JSONResponse:
    return JSONResponse({"events": SECURITY_LOG[-50:]})


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Inspect the latest user turn, then stream the model reply from Ollama.

    A blocked message never reaches Ollama; a flagged (suspicious) one is logged
    but still answered, because refusing every injection attempt outright would
    make the assistant unusable. The decision lives in app/security.py.
    """
    last_user = next(
        (m.get("content", "") for m in reversed(req.messages) if m.get("role") == "user"),
        "",
    )
    verdict = inspect(last_user)

    if verdict.severity != Severity.SAFE:
        SECURITY_LOG.append(
            {"severity": verdict.severity.value, "message": last_user[:120], "reasons": verdict.reasons}
        )

    if verdict.blocked:
        # Return the refusal as a single SSE-style chunk so the UI handles it
        # exactly like a normal streamed reply.
        def blocked_stream():
            payload = {"delta": BLOCK_MESSAGE, "done": True, "blocked": True, "reasons": verdict.reasons}
            yield f"data: {json.dumps(payload)}\n\n"

        return StreamingResponse(blocked_stream(), media_type="text/event-stream")

    async def proxy_stream():
        # Announce a suspicious verdict up front so the UI flags it even if the
        # upstream model errors mid-stream.
        if verdict.severity == Severity.SUSPICIOUS:
            yield f"data: {json.dumps({'delta': '', 'flagged': True, 'reasons': verdict.reasons})}\n\n"
        body = {"model": MODEL, "messages": req.messages, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        err = {"delta": f"Inference server error ({resp.status_code}): {text.decode()[:200]}", "done": True, "error": True}
                        yield f"data: {json.dumps(err)}\n\n"
                        return
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("message", {}).get("content", "")
                        done = chunk.get("done", False)
                        out = {"delta": delta, "done": done}
                        if verdict.severity == Severity.SUSPICIOUS:
                            out["flagged"] = True
                        yield f"data: {json.dumps(out)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = {
                "delta": f"Could not reach the inference server at {OLLAMA_URL}. "
                f"Is Ollama running and the model created? ({exc})",
                "done": True,
                "error": True,
            }
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(proxy_stream(), media_type="text/event-stream")
