"""
chat_sessions.py
----------------
Manages persistent AI chat sessions for the MLI Fleet Intelligence AI.
Sessions are stored as individual JSON files in a 'chat_sessions/' directory,
mirroring Gemini's "recent chats" experience.

Each session file contains:
  {
    "id":         str  — 8-char UUID hex
    "title":      str  — auto-set from first user message
    "created_at": str  — ISO-8601 timestamp
    "updated_at": str  — ISO-8601 timestamp
    "messages":   list — [{role, content, image_name?}]
  }
"""

from __future__ import annotations
import json
import os
import uuid
import glob
from datetime import datetime, timedelta

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_sessions")


def _session_path(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")


def _ensure_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_session(title: str = "New Chat") -> dict:
    """Create and persist a new empty session; return it."""
    _ensure_dir()
    now = datetime.now().isoformat()
    session = {
        "id":         uuid.uuid4().hex[:8],
        "title":      title,
        "created_at": now,
        "updated_at": now,
        "messages":   [],
    }
    _save(session)
    return session


def load_session(session_id: str) -> dict | None:
    """Load a session by ID, or return None if not found."""
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            return None
    return None


def save_session(session: dict):
    """Persist a session dict to disk (updates updated_at)."""
    session["updated_at"] = datetime.now().isoformat()
    _save(session)


def _save(session: dict):
    _ensure_dir()
    with open(_session_path(session["id"]), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def delete_session(session_id: str):
    """Delete a session file."""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)


def rename_session(session_id: str, new_title: str):
    """Rename a session's title."""
    session = load_session(session_id)
    if session:
        session["title"] = new_title.strip() or session["title"]
        save_session(session)


def toggle_pin(session_id: str) -> bool:
    """Toggle a session's pinned state; return new state."""
    session = load_session(session_id)
    if session:
        session["pinned"] = not session.get("pinned", False)
        save_session(session)
        return session["pinned"]
    return False


def list_sessions() -> list[dict]:
    """
    Return all sessions sorted newest-first, with a 'group' label attached:
    'Today', 'Yesterday', 'Last 7 Days', 'Older'.
    """
    _ensure_dir()
    sessions = []
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            s = json.load(open(os.path.join(SESSIONS_DIR, fname), encoding="utf-8"))
            sessions.append(s)
        except Exception:
            continue

    sessions.sort(
        key=lambda s: (not s.get("pinned", False), s.get("updated_at", "")),
        reverse=False,
    )
    # Reverse within non-pinned (pinned first, then newest-first)
    pinned = [s for s in sessions if s.get("pinned")]
    unpinned = [s for s in sessions if not s.get("pinned")]
    unpinned.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    sessions = pinned + unpinned

    now   = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago  = today - timedelta(days=7)

    for s in sessions:
        if s.get("pinned"):
            s["_group"] = "📌 Pinned"
            continue
        try:
            dt = datetime.fromisoformat(s["updated_at"]).date()
        except Exception:
            dt = today
        if dt == today:
            s["_group"] = "Today"
        elif dt == yesterday:
            s["_group"] = "Yesterday"
        elif dt >= week_ago:
            s["_group"] = "Last 7 Days"
        else:
            s["_group"] = "Older"

    return sessions


# ── Helpers ───────────────────────────────────────────────────────────────────

def auto_title(first_user_message: str, max_len: int = 38) -> str:
    """Generate a short session title from the first user message using Gemini."""
    import streamlit as st

    text = first_user_message.strip().replace("\n", " ")
    fallback = text[:max_len] + ("…" if len(text) > max_len else "")

    # Try AI-generated title
    try:
        key = st.session_state.get("gemini_key")
        if not key:
            return fallback

        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            "Summarize the following user message into a short title "
            "(3-6 words max, no quotes, no punctuation at the end). "
            "Just return the title, nothing else.\n\n"
            f"Message: {text[:200]}"
        )
        title = resp.text.strip().strip('"').strip("'").strip(".")
        if title and len(title) < 60:
            return title
    except Exception:
        pass

    return fallback
