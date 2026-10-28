"""FastAPI + Socket.IO server for IELTS Speaking Practice.

Public app: every visitor gets an isolated VoiceSession keyed by socket id, so
audio, transcripts, and panels never leak between concurrent candidates.
"""
import asyncio
import base64
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager

import socketio
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import store
from logger import log
from voice import VoiceSession

MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "5"))
UI_TOOLS = {
    "start_test",
    "next_question",
    "repeat_question",
    "finish_test",
    "set_goal",
    "get_progress",
}


def _parse_origins():
    raw = (os.getenv("CORS_ORIGINS") or "*").strip()
    if not raw or raw == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


_ORIGINS = _parse_origins()
_fastapi_origins = ["*"] if _ORIGINS == "*" else _ORIGINS

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_ORIGINS)
sessions: dict[str, VoiceSession] = {}


def _live_sessions() -> list[VoiceSession]:
    return [s for s in sessions.values() if s.task and not s.task.done()]


@asynccontextmanager
async def lifespan(app):
    ok = False
    try:
        ok = store.init()
    except Exception as e:
        log.warning(f"[STARTUP] store init failed: {e}")
    log.info(
        f"[STARTUP] ready — db={'supabase' if ok else 'jsonl fallback'}, "
        f"max_sessions={MAX_SESSIONS}, model={os.getenv('LIVE_MODEL', 'default')}"
    )
    yield
    for s in list(sessions.values()):
        try:
            await s.stop()
        except Exception:
            pass
    sessions.clear()


app = FastAPI(title="IELTS Speaking Practice", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_fastapi_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/status")
@app.head("/status")
async def status():
    return {
        "ok": True,
        "app": "ielts-speaking-practice",
        "sessions": len(_live_sessions()),
        "max_sessions": MAX_SESSIONS,
        "db": store.db_active(),
        "time": time.time(),
    }


app_socketio = socketio.ASGIApp(sio, app)


# ── socket lifecycle ────────────────────────────────────────────

@sio.event
async def connect(sid, environ):
    log.info(f"[SOCKET] connect {sid[:8]}")
    await sio.emit("connection_state", {"connected": True, "reason": "connected"}, room=sid)


@sio.event
async def disconnect(sid):
    log.info(f"[SOCKET] disconnect {sid[:8]}")
    session = sessions.pop(sid, None)
    if session:
        try:
            await session.stop()
        except Exception as e:
            log.warning(f"[SOCKET] stop failed: {e}")


# ── voice session control ───────────────────────────────────────

@sio.on("start_audio")
async def start_audio(sid, data=None):
    data = data or {}
    client_id = str(data.get("client_id") or "").strip()[:64]

    existing = sessions.get(sid)
    if existing and existing.task and not existing.task.done():
        if client_id:
            existing.client_id = client_id
            existing.examiner.client_id = client_id
        return {"ok": True, "state": "already_running"}

    if len(_live_sessions()) >= MAX_SESSIONS:
        msg = "All practice rooms are busy right now. Please try again in a minute."
        await sio.emit("error", {"msg": msg, "message": msg}, room=sid)
        return {"ok": False, "error": "max_sessions"}

    session = VoiceSession(sio, sid, client_id)
    sessions[sid] = session
    session.start()
    log.info(f"[START] session for {sid[:8]} (client={client_id[:8] or '-'})")
    return {"ok": True, "state": "started"}


@sio.on("stop_audio")
async def stop_audio(sid, data=None):
    session = sessions.pop(sid, None)
    if session:
        await session.stop()
        log.info(f"[STOP] session stopped for {sid[:8]}")
    return {"ok": True}


@sio.on("browser_audio")
async def browser_audio(sid, data):
    session = sessions.get(sid)
    if not session or not data:
        return
    raw = data.get("audio")
    if raw is None:
        return
    try:
        if isinstance(raw, list):
            pcm = bytes(raw)
        elif isinstance(raw, str):
            pcm = base64.b64decode(raw)
        else:
            pcm = bytes(raw)
    except Exception:
        return
    session.feed_browser_audio(pcm)


# ── UI-triggered tools (same 7-tool world, model narrates result) ──

@sio.on("run_ielts_tool")
async def run_ielts_tool(sid, data=None):
    data = data or {}
    name = str(data.get("tool") or "").strip()
    args = data.get("args") or {}
    session = sessions.get(sid)

    if not session or not (session.task and not session.task.done()):
        msg = "Start the voice session first, then use the test controls."
        await sio.emit("error", {"msg": msg, "message": msg}, room=sid)
        return {"ok": False, "error": "no_session"}

    if name not in UI_TOOLS:
        msg = f"'{name}' is not available from the interface."
        await sio.emit("error", {"msg": msg, "message": msg}, room=sid)
        return {"ok": False, "error": "tool_not_allowed"}

    result = await session.run_ui_tool(name, args)
    return result


@sio.on("ping")
async def ping(sid, data=None):
    return {"pong": time.time()}


def main():
    port = int(os.getenv("PORT", "8000"))
    log.info(f"[MAIN] starting on 0.0.0.0:{port}")
    uvicorn.run(
        app_socketio,
        host="0.0.0.0",
        port=port,
        ws_ping_interval=25,
        ws_ping_timeout=20,
    )


if __name__ == "__main__":
    main()
