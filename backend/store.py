"""Persistence for IELTS practice: Supabase Postgres, local JSONL fallback.

Tables (created on startup when SUPABASE_DB_URL is configured):
  ielts_clients   — anonymous per-browser progress (client_id PK)
  ielts_sessions  — one row per finished test
  ielts_answers   — one row per evaluated answer
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from logger import log

DATA_DIR = Path("backend/ielts_data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

_CONN = None
_LOCK = threading.Lock()
_READY = False

DDL = [
    """
    CREATE TABLE IF NOT EXISTS ielts_clients (
        client_id TEXT PRIMARY KEY,
        target_band DOUBLE PRECISION DEFAULT 7.0,
        exam_date TEXT,
        average_bands JSONB DEFAULT '{}',
        total_sessions INTEGER DEFAULT 0,
        speaking_sessions INTEGER DEFAULT 0,
        streak_days INTEGER DEFAULT 0,
        last_session_date TEXT,
        weak_areas JSONB DEFAULT '[]',
        strong_areas JSONB DEFAULT '[]',
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )""",
    """
    CREATE TABLE IF NOT EXISTS ielts_sessions (
        id SERIAL PRIMARY KEY,
        client_id TEXT NOT NULL,
        mode TEXT DEFAULT 'full',
        part_scores JSONB DEFAULT '{}',
        overall_band DOUBLE PRECISION,
        answer_count INTEGER DEFAULT 0,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ DEFAULT now(),
        report JSONB DEFAULT '{}'
    )""",
    """
    CREATE TABLE IF NOT EXISTS ielts_answers (
        id SERIAL PRIMARY KEY,
        session_id TEXT,
        client_id TEXT,
        part INTEGER DEFAULT 1,
        question TEXT DEFAULT '',
        answer_text TEXT DEFAULT '',
        corrected_transcript TEXT DEFAULT '',
        band_scores JSONB DEFAULT '{}',
        overall_band DOUBLE PRECISION,
        grammar_errors JSONB DEFAULT '[]',
        vocabulary_feedback JSONB DEFAULT '{}',
        pronunciation JSONB DEFAULT '{}',
        word_count INTEGER DEFAULT 0,
        filler_words_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
]


def _connect():
    global _CONN
    url = os.getenv("SUPABASE_DB_URL", "") or os.getenv("DATABASE_URL", "")
    if not url:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(url, connect_timeout=10)
        return conn
    except Exception as e:
        log.warning(f"[STORE] Supabase connect failed: {e} — using file fallback")
        return None


def init() -> bool:
    """Create tables once at startup. Returns True when DB is active."""
    global _CONN, _READY
    with _LOCK:
        if _READY:
            return _CONN is not None
        _CONN = _connect()
        if _CONN:
            try:
                with _CONN.cursor() as cur:
                    for ddl in DDL:
                        cur.execute(ddl)
                _CONN.commit()
                log.info("[STORE] Supabase active — ielts_* tables ready")
            except Exception as e:
                log.warning(f"[STORE] table creation failed: {e} — file fallback")
                try:
                    _CONN.rollback()
                except Exception:
                    pass
                _CONN = None
        if not _CONN:
            log.info("[STORE] file fallback active (backend/ielts_data/*.jsonl)")
        _READY = True
        return _CONN is not None


def db_active() -> bool:
    return _CONN is not None


def _execute(sql: str, params=None) -> bool:
    if not _CONN:
        return False
    with _LOCK:
        try:
            with _CONN.cursor() as cur:
                cur.execute(sql, params)
            _CONN.commit()
            return True
        except Exception as e:
            log.warning(f"[STORE] exec failed: {e}")
            try:
                _CONN.rollback()
            except Exception:
                pass
            return False


def _fetch(sql: str, params=None):
    if not _CONN:
        return None
    with _LOCK:
        try:
            with _CONN.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            _CONN.commit()
            return rows
        except Exception as e:
            log.warning(f"[STORE] fetch failed: {e}")
            try:
                _CONN.rollback()
            except Exception:
                pass
            return None


def _append_jsonl(name: str, entry: dict):
    with open(DATA_DIR / name, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _read_jsonl(name: str, limit: int = 50) -> list:
    path = DATA_DIR / name
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f.readlines()[-limit:]:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


# ── client progress ─────────────────────────────────────────────

def get_client(client_id: str) -> dict | None:
    if not client_id:
        return None
    if db_active():
        rows = _fetch("SELECT * FROM ielts_clients WHERE client_id = %s", (client_id,))
        if rows is not None:
            row = rows[0] if rows else None
            if row:
                for k in ("average_bands", "weak_areas", "strong_areas"):
                    if isinstance(row.get(k), str):
                        try:
                            row[k] = json.loads(row[k])
                        except Exception:
                            row[k] = []
            return row
    # file fallback: search JSONL
    for entry in reversed(_read_jsonl("clients.jsonl", 500)):
        if entry.get("client_id") == client_id:
            return entry
    return None


def upsert_client(client_id: str, fields: dict):
    if not client_id:
        return
    if db_active():
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in fields)
        params = [client_id] + list(fields.values())
        _execute(
            f"""INSERT INTO ielts_clients (client_id, {cols})
                VALUES (%s, {placeholders})
                ON CONFLICT (client_id) DO UPDATE SET {updates}, updated_at = now()""",
            params,
        )
        return
    # file fallback: rewrite last known state as a new JSONL row (get_client takes latest)
    existing = get_client(client_id) or {"client_id": client_id}
    existing.update(fields)
    existing["updated_at"] = datetime.now().isoformat()
    _append_jsonl("clients.jsonl", existing)


# ── sessions & answers ──────────────────────────────────────────

def save_session(session: dict, answers: list) -> int | None:
    """Persist a finished test. Returns session id (DB) or None (file mode)."""
    session_id = None
    if db_active():
        rows = _fetch(
            """INSERT INTO ielts_sessions
               (client_id, mode, part_scores, overall_band, answer_count, started_at, report)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                session.get("client_id", ""),
                session.get("mode", "full"),
                json.dumps(session.get("part_scores", {})),
                session.get("overall_band"),
                len(answers),
                session.get("started_at"),
                json.dumps(session.get("report", {})),
            ),
        )
        if rows:
            session_id = rows[0]["id"]
        for a in answers:
            _execute(
                """INSERT INTO ielts_answers
                   (session_id, client_id, part, question, answer_text, corrected_transcript,
                    band_scores, overall_band, grammar_errors, vocabulary_feedback,
                    pronunciation, word_count, filler_words_count)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    session_id,
                    session.get("client_id", ""),
                    a.get("part", 1),
                    a.get("question", ""),
                    (a.get("answer_text") or "")[:20000],
                    (a.get("corrected_transcript") or "")[:20000],
                    json.dumps(a.get("band_scores", {})),
                    a.get("overall_band"),
                    json.dumps(a.get("grammar_errors", [])),
                    json.dumps(a.get("vocabulary_feedback", {})),
                    json.dumps(a.get("pronunciation_detail", {})),
                    a.get("word_count", 0),
                    a.get("filler_words_count", 0),
                ),
            )
    else:
        _append_jsonl("sessions.jsonl", {**session, "answers": len(answers)})
        for a in answers:
            _append_jsonl("answers.jsonl", {**a, "client_id": session.get("client_id", "")})
    log.info(f"[STORE] session saved (id={session_id}, answers={len(answers)})")
    return session_id


def get_history(client_id: str, limit: int = 20) -> list:
    if db_active():
        rows = _fetch(
            """SELECT id, mode, part_scores, overall_band, answer_count, finished_at
               FROM ielts_sessions WHERE client_id = %s
               ORDER BY finished_at DESC LIMIT %s""",
            (client_id, limit),
        )
        if rows is not None:
            return rows
    entries = [e for e in _read_jsonl("sessions.jsonl", 500) if e.get("client_id") == client_id]
    return entries[:limit]
