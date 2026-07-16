"""WebSocket: stream per-frame overlay + metrics while a session is processed.

Client connects to /ws/sessions/{session_id}. The server runs the (blocking,
CPU-bound) pipeline in a worker thread and forwards each frame payload to the
client over the socket. A sentinel {"done": true} is sent at the end.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.workers.processor import process_session, request_cancel, request_pause, request_resume

logger = logging.getLogger("app.ws")

router = APIRouter()

_SENTINEL = object()


@router.websocket("/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: int):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    # Optional query params: ?max_frames=N&overlay=1
    # Overlay (server-rendered JPEG) is OFF by default — the frontend renders
    # the overlay on the native <video> using the streamed tracks.
    qp = websocket.query_params
    max_frames = int(qp["max_frames"]) if qp.get("max_frames") else None
    include_overlay = qp.get("overlay", "0") == "1"

    def emit(payload: dict) -> None:
        # Called from the worker thread; hand off to the event loop safely.
        try:
            loop.call_soon_threadsafe(queue.put_nowait, payload)
        except Exception:
            pass

    def run() -> dict:
        try:
            return process_session(session_id, emit=emit, max_frames=max_frames, include_overlay=include_overlay)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    worker = loop.run_in_executor(None, run)

    async def receiver() -> None:
        """Listen for client control messages (pause/resume) so paused video
        actually pauses detection. Client disconnect raises WebSocketDisconnect."""
        while True:
            msg = await websocket.receive_json()
            action = (msg or {}).get("action")
            if action == "pause":
                request_pause(session_id)
            elif action == "resume":
                request_resume(session_id)

    recv_task = asyncio.ensure_future(receiver())

    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            await websocket.send_json(item)
        summary = await worker
        await websocket.send_json({"done": True, **(summary or {})})
    except WebSocketDisconnect:
        logger.info("WS client disconnected for session %s — cancelling.", session_id)
        request_cancel(session_id)  # stop the worker thread; partial data discarded
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("WS error for session %s: %s", session_id, e)
        request_cancel(session_id)
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        recv_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
