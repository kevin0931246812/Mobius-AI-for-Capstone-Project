"""
modules/mobius_ai.py
--------------------
Möbius AI Intelligence Panel — Floating chat popup available on all pages.

Uses pure CSS with :has() selectors targeting [data-testid="stLayoutWrapper"]
to lift Streamlit containers out of document flow and position them as fixed
overlays, creating a true floating chat widget.

Provides:
  - Fixed floating action button (bottom-right, always visible)
  - Toggle-able popup chat window (fixed position, overlays page content)
  - API key entry (Connect Möbius AI card)
  - Persistent chat sessions (Today / Yesterday / Last 7 Days / Older)
  - Image + file attachment (PDF, Excel, CSV, TXT)
  - Full database context injection on every query
"""
from __future__ import annotations

import os
import json
import base64

import streamlit as st

from ai_context import build_ai_context
from anomaly_manager import load_archive
from chat_sessions import (
    create_session, load_session, save_session,
    delete_session, list_sessions, auto_title,
    rename_session, toggle_pin,
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSIGHTS_PATH  = os.path.join(_BASE, "customer_insights.json")
GIF_PATH       = os.path.join(_BASE, "Mobious.gif")
DATA_FILE_PATH = os.path.join(_BASE, "MLI Capstone Data.xlsx")
_KEY_FILE      = os.path.join(_BASE, ".gemini_key")


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data
def _load_customer_insights(data_mtime: float) -> dict:
    if os.path.exists(INSIGHTS_PATH):
        try:
            with open(INSIGHTS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _load_saved_key() -> str | None:
    """Load the API key from local file (persists across restarts)."""
    if os.path.exists(_KEY_FILE):
        try:
            with open(_KEY_FILE) as f:
                key = f.read().strip()
                if key:
                    return key
        except OSError:
            pass
    return None


def _save_key(key: str) -> None:
    """Save the API key to local file for future sessions."""
    try:
        with open(_KEY_FILE, "w") as f:
            f.write(key)
    except OSError:
        pass


def _logo_b64() -> str:
    """Return base64-encoded mobius_logo.png, or '' if missing."""
    path = os.path.join(_BASE, "mobius_logo.png")
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


def _fab_logo_b64() -> str:
    """Return base64-encoded mobius_fab_logo.png (the triangle logo), or ''."""
    path = os.path.join(_BASE, "mobius_fab_logo.png")
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


# ── Floating CSS ──────────────────────────────────────────────────────────────
# Uses :has() to target Streamlit's [data-testid="stLayoutWrapper"] that
# contains our hidden marker divs, then repositions them as fixed overlays.
# DOM path confirmed: DIV#marker → stMarkdownContainer → stMarkdown →
#   stElementContainer → stVerticalBlock → stLayoutWrapper

def _build_float_css() -> str:
    """Build CSS with the FAB logo injected as background-image."""
    fab_b64 = _fab_logo_b64()
    # Build the button background rule
    if fab_b64:
        fab_bg = (
            f'background: url("data:image/png;base64,{fab_b64}") '
            f'center/contain no-repeat transparent !important;'
        )
        fab_text = 'color: transparent !important; font-size: 0 !important;'
    else:
        fab_bg = 'background: linear-gradient(135deg, #0052cc 0%, #38bdf8 100%) !important;'
        fab_text = 'color: white !important; font-size: 28px !important;'

    return f"""
<style>
/* ═══════════════════════════════════════════════════════════════════════════ */
/*   FLOATING ACTION BUTTON (FAB)                                            */
/* ═══════════════════════════════════════════════════════════════════════════ */

/* Collapse document-flow space from floating containers */
div:has(> [data-testid="stLayoutWrapper"]:has(#mobius-fab-marker)),
div:has(> [data-testid="stLayoutWrapper"]:has(#mobius-popup-marker)) {{
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
}}

/* Float the FAB container to fixed bottom-right */
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker),
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker) *:not(button) {{
    position: static;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker) {{
    position: fixed !important;
    bottom: 24px;
    right: 28px;
    z-index: 999999;
    width: auto !important;
    max-width: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 !important;
    min-height: auto !important;
    overflow: visible !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
}}

/* Style the FAB button — show triangle logo, knock out black */
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker) button {{
    width: 72px !important;
    height: 72px !important;
    min-height: 72px !important;
    border-radius: 0 !important;
    {fab_bg}
    border: none !important;
    {fab_text}
    padding: 6px !important;
    box-shadow: none !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker) button:hover {{
    transform: scale(1.1) !important;
    filter: brightness(1.3) !important;
}}

/* No label below FAB */

/* Hide marker text/container inside FAB */
[data-testid="stLayoutWrapper"]:has(#mobius-fab-marker) [data-testid="stMarkdown"] {{
    display: none !important;
}}

@keyframes mobius-fab-pulse {{
    0%, 100% {{ box-shadow: 0 6px 28px rgba(200,120,0,0.4), 0 0 0 0 rgba(255,165,0,0.25); }}
    50%      {{ box-shadow: 0 6px 28px rgba(200,120,0,0.4), 0 0 0 14px rgba(255,165,0,0); }}
}}


/* ═══════════════════════════════════════════════════════════════════════════ */
/*   POPUP CHAT WINDOW                                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */

/* Float the popup container as a fixed overlay card */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) {{
    position: fixed !important;
    bottom: 12px;
    right: 12px;
    z-index: 999998;
    width: 65vw !important;
    max-width: 1300px !important;
    max-height: calc(100vh - 24px);
    overflow: auto;
    background: rgba(12, 14, 20, 0.96) !important;
    backdrop-filter: blur(32px) saturate(180%) !important;
    border-radius: 22px !important;
    border: 1px solid rgba(212,135,28,0.15) !important;
    box-shadow:
        0 32px 100px rgba(0,0,0,0.7),
        0 0 40px rgba(212,135,28,0.06) !important;
    padding: 14px 20px 14px !important;
    display: flex !important;
    flex-direction: column !important;
}}
/* Strip any extra borders from Streamlit inner wrappers */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stMain"],
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stMainBlockContainer"],
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) > div {{
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
}}

/* Clean up form styling inside popup */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stForm"] {{
    border: none !important;
    padding: 0 !important;
}}

/* ── Sidebar column scroll + style ── */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
    max-height: calc(85vh - 100px) !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: none !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    padding-right: 12px !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child::-webkit-scrollbar {{
    display: none !important;
}}

/* Sidebar session buttons: flat text (secondary only) */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child button[kind="secondary"] {{
    font-size: 11.5px !important;
    padding: 5px 8px !important;
    min-height: 30px !important;
    height: auto !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    background: transparent !important;
    border: none !important;
    color: rgba(255,255,255,0.65) !important;
    border-radius: 6px !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child button[kind="secondary"]:hover {{
    background: rgba(255,255,255,0.05) !important;
    color: rgba(255,255,255,0.9) !important;
}}
/* Active session (primary in row) — compact + left accent */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child button[kind="primary"] {{
    font-size: 11.5px !important;
    padding: 5px 8px !important;
    min-height: 30px !important;
    height: auto !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    border-radius: 6px !important;
}}

/* Sidebar captions: tighter spacing */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child [data-testid="stCaptionContainer"] {{
    margin-top: 8px !important;
    margin-bottom: 2px !important;
}}

/* ── ⋮ column: hidden by default, appears on session row hover ── */
/* Only target rows INSIDE the sidebar (first column), not the main chat column */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {{
    opacity: 0 !important;
    transition: opacity 0.15s !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) * {{
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:hover > [data-testid="stColumn"]:nth-child(2) {{
    opacity: 1 !important;
}}

/* ── Three-dot popover ⋮ trigger ── */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stPopover"] > button {{
    background: transparent !important;
    border: none !important;
    width: 28px !important;
    min-width: 28px !important;
    max-width: 28px !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 !important;
    display: block !important;
    overflow: hidden !important;
    cursor: pointer !important;
    position: relative !important;
}}
/* Hide all children (text + chevron SVG) */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stPopover"] > button > * {{
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    position: absolute !important;
}}
/* Inject ⋮ via pseudo-element */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stPopover"] > button::before {{
    content: "⋮" !important;
    visibility: visible !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 28px !important;
    height: 28px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    color: rgba(255,255,255,0.35) !important;
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stPopover"] > button:hover::before {{
    color: rgba(255,255,255,0.7) !important;
}}

/* Popover dropdown body */
[data-testid="stPopoverBody"] {{
    background: rgba(20, 22, 30, 0.98) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    padding: 4px !important;
    min-width: 120px !important;
    max-width: 140px !important;
    backdrop-filter: blur(20px) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
}}
[data-testid="stPopoverBody"] button {{
    background: transparent !important;
    border: none !important;
    border-radius: 4px !important;
    color: rgba(255,255,255,0.75) !important;
    font-size: 12px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 5px 10px !important;
    min-height: 26px !important;
    height: auto !important;
    box-shadow: none !important;
}}
[data-testid="stPopoverBody"] button:hover {{
    background: rgba(255,255,255,0.06) !important;
    color: rgba(255,255,255,0.95) !important;
}}
[data-testid="stPopoverBody"] hr {{
    border-color: rgba(255,255,255,0.06) !important;
    margin: 2px 0 !important;
}}
[data-testid="stPopoverBody"] [data-testid="stTextInput"] input {{
    font-size: 11px !important;
    padding: 4px 8px !important;
    min-height: 26px !important;
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 4px !important;
    color: rgba(255,255,255,0.8) !important;
}}

/* ── Chat message layout: user = right, AI = left ── */

/* User messages → right-aligned with bubble */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
    flex-direction: row-reverse !important;
    background: transparent !important;
    border: none !important;
    margin-left: auto !important;
    width: fit-content !important;
    max-width: 80% !important;
    gap: 8px !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] {{
    background: rgba(40, 80, 160, 0.25) !important;
    border-radius: 16px 16px 4px 16px !important;
    padding: 10px 14px !important;
    text-align: left !important;
}}

/* AI messages → left-aligned, clean */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
    background: transparent !important;
    border: none !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stMarkdownContainer"] {{
    background: transparent !important;
    padding: 4px 0 !important;
}}
/* Hide ALL scrollbars inside popup but keep scrolling */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) * {{
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) *::-webkit-scrollbar {{
    display: none !important;
}}


/* ── Clean input bar ── */

/* Hide "Press Enter to submit form" helper text */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stForm"] [data-testid="InputInstructions"] {{
    display: none !important;
}}

/* Vertically align form columns */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stForm"] [data-testid="stHorizontalBlock"] {{
    align-items: flex-end !important;
    gap: 6px !important;
}}

/* Auto-expanding textarea */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stForm"] textarea {{
    min-height: 38px !important;
    max-height: 300px !important;
    height: auto !important;
    resize: none !important;
    overflow-y: auto !important;
    padding: 8px 12px !important;
    line-height: 1.4 !important;
}}

/* ── File uploader → 📎 icon button ── */

/* Constrain the uploader column */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploader"] {{
    max-width: 36px !important;
}}

/* Make the dropzone invisible — just a flat click target */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploaderDropzone"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    width: 32px !important;
    height: 32px !important;
    min-height: 32px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    overflow: hidden !important;
}}
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploaderDropzone"]:hover {{
    background: transparent !important;
    border: none !important;
}}

/* Hide ALL text inside the dropzone (drag-and-drop text, file info) */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploaderDropzone"] > div {{
    display: none !important;
}}

/* Hide "Browse files" text but keep the button as an invisible clickable overlay */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploaderDropzone"] button {{
    position: absolute !important;
    width: 32px !important;
    height: 32px !important;
    opacity: 0 !important;
    cursor: pointer !important;
    z-index: 2 !important;
}}

/* Show 📎 emoji via pseudo-element on the dropzone */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploaderDropzone"]::after {{
    content: "📎" !important;
    font-size: 18px !important;
    position: absolute !important;
    pointer-events: none !important;
    opacity: 0.5 !important;
}}

/* Hide the file size limit text */
[data-testid="stLayoutWrapper"]:has(#mobius-popup-marker) [data-testid="stFileUploader"] small {{
    display: none !important;
}}

/* ── Global: move Streamlit tooltip above button (renders in portal) ── */
[data-testid="stTooltipContent"] {{
    margin-top: -60px !important;
}}
</style>
"""


# ── Public entry point ────────────────────────────────────────────────────────

def render():
    """Render the Möbius AI Intelligence panel as a floating popup."""

    # ── Initialise popup state ────────────────────────────────────────────────
    if "mobius_chat_open" not in st.session_state:
        st.session_state.mobius_chat_open = False

    # ── Inject float CSS (must come early) ────────────────────────────────────
    st.markdown(_build_float_css(), unsafe_allow_html=True)

    # ── Data context ──────────────────────────────────────────────────────────
    try:
        data_mtime = os.path.getmtime(DATA_FILE_PATH)
    except FileNotFoundError:
        data_mtime = 0

    all_insights    = _load_customer_insights(data_mtime)
    total_customers = sum(len(v) for v in all_insights.values())
    total_anomalies = sum(len(c.get("anomalies", [])) for v in all_insights.values() for c in v)

    current_page = st.session_state.get("current_page", "tracking")
    page_labels = {
        "systematic_concept": "🔬 Systematic Concept",
        "control_tower":  "🏢 Control Tower",
        "tracking":       "📦 Tracking",
        "real_world_sim": "💰 Real World Sim",
        "simulation":     "🌍 Fleet Optimization",
    }
    page_label = page_labels.get(current_page, current_page)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. POPUP CHAT WINDOW (only when open)
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.mobius_chat_open:
        with st.container(border=True):
            # Hidden marker for CSS :has() targeting
            st.markdown(
                '<div id="mobius-popup-marker"></div>',
                unsafe_allow_html=True,
            )
            _render_popup_content(
                total_customers, total_anomalies, page_label, current_page
            )

    # ══════════════════════════════════════════════════════════════════════════
    # 2. FLOATING ACTION BUTTON (only when chat is CLOSED)
    # ══════════════════════════════════════════════════════════════════════════
    if not st.session_state.mobius_chat_open:
        with st.container(border=True):
            # Hidden marker for CSS :has() targeting
            st.markdown(
                '<div id="mobius-fab-marker"></div>',
                unsafe_allow_html=True,
            )
            if st.button("\u200b", key="mobius_fab_btn", help="Möbius AI Chat"):
                st.session_state.mobius_chat_open = True
                st.rerun()


# ── Popup content ─────────────────────────────────────────────────────────────

def _render_popup_content(
    total_customers: int,
    total_anomalies: int,
    page_label: str,
    current_page: str,
):
    """Render the full chat UI inside the floating popup with sidebar."""

    logo = _logo_b64()

    # ── Sidebar toggle state ──────────────────────────────────────────────────
    if "mobius_sidebar_open" not in st.session_state:
        st.session_state.mobius_sidebar_open = True

    # ── Minimal top controls: ☰ (left) ... 🔌 Disconnect + ✕ (right) ─────────
    _toggle_col, _spacer, _disc_col, _close_col = st.columns([0.4, 7.2, 1.2, 0.3])
    with _toggle_col:
        if st.button("☰", key="mobius_sidebar_toggle", type="tertiary",
                     help="Toggle sidebar"):
            st.session_state.mobius_sidebar_open = not st.session_state.mobius_sidebar_open
            st.rerun()
    with _disc_col:
        if st.session_state.get("gemini_key"):
            if st.button("🔌 Disconnect", key="disconnect_api", type="tertiary",
                         help="Disconnect API key"):
                st.session_state.pop("gemini_key", None)
                key_file = os.path.join(os.path.dirname(__file__), "..", ".gemini_key")
                try:
                    os.remove(key_file)
                except FileNotFoundError:
                    pass
                st.rerun()
    with _close_col:
        if st.button("✕", key="mobius_close_btn", type="tertiary",
                     help="Close Möbius AI"):
            st.session_state.mobius_chat_open = False
            st.rerun()

    # ── No API key → try loading from saved file, then show connect bar ───────
    if not st.session_state.get("gemini_key"):
        saved = _load_saved_key()
        if saved:
            st.session_state["gemini_key"] = saved
            st.rerun()
        st.caption(
            "🔗 Paste your Gemini API key to enable the AI chat panel."
        )
        _key_col, _btn_col = st.columns([3, 1])
        with _key_col:
            _typed_key = st.text_input(
                "API Key",
                type="password",
                placeholder="AIza...",
                label_visibility="collapsed",
                key="popup_key_input",
            )
        with _btn_col:
            if st.button("Go", type="primary",
                         use_container_width=True, key="popup_connect"):
                if _typed_key.strip():
                    st.session_state["gemini_key"] = _typed_key.strip()
                    _save_key(_typed_key.strip())
                    st.success("✅ Connected!")
                    st.rerun()
                else:
                    st.error("Paste a key first.")
        st.link_button(
            "Get free key →", "https://aistudio.google.com/app/apikey",
        )
        return   # stop here — no chat without a key

    # ══════════════════════════════════════════════════════════════════════════
    # API KEY IS PRESENT — Full chat UI with sidebar
    # ══════════════════════════════════════════════════════════════════════════

    # ── Session initialisation ────────────────────────────────────────────────
    if "active_session_id" not in st.session_state:
        first_sessions = list_sessions()
        if first_sessions:
            st.session_state.active_session_id = first_sessions[0]["id"]
            st.session_state.session_messages   = first_sessions[0].get("messages", [])
        else:
            new_sess = create_session("New Chat")
            st.session_state.active_session_id = new_sess["id"]
            st.session_state.session_messages   = []

    # ── Layout: [Sidebar | Main Chat] ─────────────────────────────────────────
    sidebar_open = st.session_state.mobius_sidebar_open

    if sidebar_open:
        sidebar_col, main_col = st.columns([0.28, 0.72], gap="small")
    else:
        sidebar_col = None
        main_col = st.container()

    # ── SIDEBAR: logo + session history ─────────────────────────────────────────
    if sidebar_open and sidebar_col is not None:
        with sidebar_col:
            # ── Branding ──────────────────────────────────────────────────────
            if logo:
                st.markdown(
                    f'<div style="text-align:center;padding:8px 0 4px;">'
                    f'<img src="data:image/png;base64,{logo}" '
                    f'style="height:90px;border-radius:6px;">'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── New Chat button ───────────────────────────────────────────────
            if st.button("➕ New Chat", use_container_width=True, type="primary",
                         key="popup_new_chat"):
                new_sess = create_session("New Chat")
                st.session_state.active_session_id = new_sess["id"]
                st.session_state.session_messages   = []
                st.rerun()

            st.markdown(
                '<hr style="margin:6px 0;border:none;border-top:1px solid rgba(255,255,255,0.08);">',
                unsafe_allow_html=True,
            )

            # ── Session list with context menus ───────────────────────────────
            all_sessions = list_sessions()
            current_group = None
            for sess in all_sessions[:15]:
                group = sess.get("_group", "Older")
                if group != current_group:
                    st.caption(group)
                    current_group = group

                is_active = sess["id"] == st.session_state.active_session_id
                is_pinned = sess.get("pinned", False)

                row_a, row_b = st.columns([4, 1])
                with row_a:
                    title = ("📌 " if is_pinned else "") + sess["title"]
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(
                        title,
                        key=f"ps_{sess['id']}",
                        use_container_width=True,
                        type=btn_type,
                        help=sess.get("updated_at", "")[:16].replace("T", " "),
                    ):
                        loaded = load_session(sess["id"])
                        st.session_state.active_session_id = sess["id"]
                        st.session_state.session_messages = (loaded or {}).get("messages", [])
                        st.rerun()
                with row_b:
                    # Three-dot context menu via popover
                    with st.popover("⋮", use_container_width=True):
                        if st.button(
                            "Share", key=f"share_{sess['id']}",
                            use_container_width=True, type="tertiary",
                        ):
                            st.toast(f"📋 Link copied!")

                        pin_label = "Unpin" if is_pinned else "Pin"
                        if st.button(
                            pin_label, key=f"pin_{sess['id']}",
                            use_container_width=True, type="tertiary",
                        ):
                            toggle_pin(sess["id"])
                            st.rerun()

                        new_name = st.text_input(
                            "rename",
                            value=sess["title"],
                            key=f"rename_{sess['id']}",
                            label_visibility="collapsed",
                            placeholder="Rename…",
                        )
                        if new_name and new_name != sess["title"]:
                            rename_session(sess["id"], new_name)
                            st.rerun()

                        st.markdown("---")

                        if st.button(
                            "Delete", key=f"pd_{sess['id']}",
                            use_container_width=True, type="tertiary",
                        ):
                            delete_session(sess["id"])
                            if sess["id"] == st.session_state.active_session_id:
                                new_sess = create_session("New Chat")
                                st.session_state.active_session_id = new_sess["id"]
                                st.session_state.session_messages   = []
                            st.rerun()


    # ── MAIN: chat window + input ─────────────────────────────────────────────
    with main_col:
        # ── Chat messages ─────────────────────────────────────────────────────
        messages = st.session_state.get("session_messages", [])

        if not messages:
            greeting = {
                "role": "assistant",
                "content": (
                    f"Hello! I have access to **{total_customers} customers**, "
                    f"contracts, R2R data, and anomaly archive.\n\n"
                    f"Currently viewing: **{page_label}**.\n\n"
                    f"What would you like to know?"
                ),
            }
            display_messages = [greeting]
        else:
            display_messages = messages

        chat_window = st.container(height=600, border=False)
        for msg in display_messages:
            with chat_window.chat_message(msg["role"]):
                if msg.get("has_image"):
                    st.caption("📎 *Image attached*")
                st.markdown(msg["content"])

        # ── Input bar: [📎] [Ask anything…] [➤] ──────────────────────────────
        with st.form("mobius_popup_form", clear_on_submit=True, border=False):
            clip_col, input_col, send_col = st.columns(
                [0.08, 1, 0.15], vertical_alignment="center"
            )
            with clip_col:
                uploaded_file = st.file_uploader(
                    "📎",
                    type=["png", "jpg", "jpeg", "webp", "gif",
                          "pdf", "xlsx", "xls", "csv", "txt"],
                    label_visibility="collapsed",
                    key="popup_file_upload",
                )
            with input_col:
                user_input = st.text_area(
                    "msg",
                    placeholder="Ask anything…",
                    label_visibility="collapsed",
                    key="popup_text_input",
                    height=38,
                )
            with send_col:
                submitted = st.form_submit_button(
                    "➤", type="primary", use_container_width=True,
                )

        # ── Process message ─────────────────────────────────────────────────
        if submitted and user_input and user_input.strip():
            _process_message(
                user_text=user_input.strip(),
                uploaded_file=uploaded_file,
                chat_window=chat_window,
                current_page=current_page,
                total_customers=total_customers,
                total_anomalies=total_anomalies,
            )


# ── Message processing ────────────────────────────────────────────────────────

def _process_message(
    user_text: str,
    uploaded_file,
    chat_window,
    current_page: str,
    total_customers: int,
    total_anomalies: int,
):
    """Process user message: show it, call Gemini, display response."""

    IMAGE_TYPES = {"png", "jpg", "jpeg", "webp", "gif"}

    img_bytes  = None
    file_text  = None
    file_label = None

    if uploaded_file:
        raw        = uploaded_file.read()
        ext        = uploaded_file.name.rsplit(".", 1)[-1].lower()
        file_label = uploaded_file.name

        if ext in IMAGE_TYPES:
            img_bytes = raw
        elif ext == "pdf":
            try:
                import io as _io, pypdf as _pypdf
                reader    = _pypdf.PdfReader(_io.BytesIO(raw))
                file_text = "\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                try:
                    import io as _io, PyPDF2 as _pdf
                    reader    = _pdf.PdfReader(_io.BytesIO(raw))
                    file_text = "\n".join(p.extract_text() or "" for p in reader.pages)
                except Exception:
                    file_text = "(PDF extraction unavailable — install pypdf)"
            except Exception as pdf_err:
                file_text = f"(PDF extraction error: {pdf_err})"
        elif ext in ("xlsx", "xls"):
            try:
                import io as _io, pandas as _pd
                df        = _pd.read_excel(_io.BytesIO(raw))
                file_text = df.to_string(index=False, max_rows=200)
            except Exception as xl_err:
                file_text = f"(Excel read error: {xl_err})"
        elif ext == "csv":
            file_text = raw.decode("utf-8", errors="replace")
        elif ext == "txt":
            file_text = raw.decode("utf-8", errors="replace")

    messages = st.session_state.get("session_messages", [])
    user_msg = {
        "role":      "user",
        "content":   user_text,
        "has_image": bool(img_bytes),
        "has_file":  bool(file_text),
        "file_name": file_label,
    }
    messages.append(user_msg)

    # Show user message immediately in chat window
    with chat_window.chat_message("user"):
        if img_bytes:
            st.caption("📎 *Image attached*")
        st.markdown(user_text)

    # Show thinking indicator
    with chat_window.chat_message("assistant"):
        thinking_ph = st.empty()
        thinking_ph.markdown("⏳ *Querying full database…*")

    session_data = load_session(st.session_state.active_session_id) or {}
    if not session_data.get("messages"):
        session_data["title"] = auto_title(user_text)

    try:
        ai_text = _call_gemini(
            user_prompt=user_text,
            messages=messages,
            image_bytes=img_bytes,
            file_text=file_text,
            current_page=current_page,
            total_customers=total_customers,
            total_anomalies=total_anomalies,
        )
        thinking_ph.markdown(ai_text)
        messages.append({"role": "assistant", "content": ai_text})
        session_data["messages"] = messages
        save_session(session_data)
        st.session_state.session_messages = messages
        st.rerun()
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            thinking_ph.error(
                "⏳ **Quota exceeded.**\n\n"
                "Get a fresh key at [aistudio.google.com](https://aistudio.google.com)."
            )
        elif "404" in err or "not found" in err.lower():
            thinking_ph.error("Model not found. Try again.")
        else:
            thinking_ph.error(f"Error: {err}")


# ── Private: Gemini call ──────────────────────────────────────────────────────

def _call_gemini(
    user_prompt: str,
    messages: list,
    image_bytes: bytes | None = None,
    file_text: str | None = None,
    *,
    current_page: str = "",
    total_customers: int = 0,
    total_anomalies: int = 0,
) -> str:
    """
    Call Gemini with full-DB context + optional image or file text.
    Page-aware: knows which dashboard page the user is currently viewing.
    """
    import google.generativeai as genai
    genai.configure(api_key=st.session_state["gemini_key"])

    # Use a known, stable model — avoids fragile auto-selection from list_models()
    selected_model = "gemini-2.5-flash"
    try:
        model = genai.GenerativeModel(selected_model)
    except Exception:
        # Fallback: try the legacy model name
        model = genai.GenerativeModel("gemini-pro")

    # Build page state from session_state (works for any page)
    page_state = {
        "current_page": current_page,
        "simulation_results": None,
    }
    if "optimal_fleet_size" in st.session_state:
        page_state["simulation_results"] = {
            "optimal_fleet_size": st.session_state["optimal_fleet_size"],
            "daily_demand_used":  st.session_state.get("sim_daily_demand"),
            "eu_exposure_pct":    st.session_state.get("sim_eu_exposure"),
        }

    ctx = build_ai_context(
        selected_item=st.session_state.get("fo_product", ""),
        focused_customer=st.session_state.get("deep_dive"),
        page_state=page_state,
        archive=load_archive(),
    )

    system = (
        "You are the MLI Fleet Intelligence AI, a senior supply chain analyst "
        "for a capstone project at ASU W. P. Carey School of Business. "
        "You have FULL access to the database: all customer order histories, "
        "contract terms, receipt-to-receipt times, anomaly records, and simulation results. "
        f"The user is currently viewing the **{current_page}** page of the dashboard. "
        "You can answer questions about ANY page: Forecasting, Tracking Return Status, "
        "Real World Simulation, or Fleet Optimization. "
        "Be specific — cite customer names, dates, quantities, and percentages. "
        "Connect findings to actionable recommendations. "
        "Be concise and professional."
    )

    history_str = ""
    for msg in messages[1:-1]:
        history_str += f"{msg['role'].title()}: {msg['content']}\n"

    file_section = ""
    if file_text:
        file_section = f"\n\n[ATTACHED FILE CONTENT]\n{file_text[:8000]}"

    text_prompt = (
        f"{system}\n\n"
        f"[FULL DATABASE SNAPSHOT]\n{json.dumps(ctx)}\n\n"
        f"Conversation so far:\n{history_str}\n"
        f"User question: {user_prompt}"
        f"{file_section}"
    )

    if image_bytes:
        import PIL.Image
        import io
        img = PIL.Image.open(io.BytesIO(image_bytes))
        contents = [text_prompt, img]
    else:
        contents = text_prompt

    response = model.generate_content(contents)

    return response.text
