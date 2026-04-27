"""
app.py
------
Möbius AI — Supply Chain Intelligence Dashboard (entry point).

This file is the **shell**: it handles global setup (page config,
background video/dots, glassmorphism CSS, data pipeline) and sidebar
navigation.  Each page's logic lives in its own module under `pages/`.

Modules:
  pages/forecasting.py          — Demand forecasting (placeholder)
  pages/real_world_sim.py       — Supply Chain Command Center
  pages/tracking.py             — Tracking Return Status
  pages/fleet_optimization.py   — Fleet Optimization Dashboard + AI chat
"""

from __future__ import annotations

# ── Imports (shell only — page-specific imports live in pages/) ────────────────
import streamlit as st
import streamlit.components.v1 as components
import os
import base64

from data_cleaner import main as run_data_pipeline_clean
from config import DATA_FILE_PATH, VIDEO_PATH


# ── Helper: video background injector ─────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_video_inject_js(video_path: str) -> str:
    """
    Return a <script> that injects a fullscreen <video> background into the
    PARENT document exactly ONCE per browser session (checked by element ID).

    Unlike st.markdown() which re-renders and flashes on every Streamlit
    rerun, this script is injected via components.html() into an iframe that
    targets window.parent.document.  The ID guard means subsequent reruns
    find the element already present and exit immediately — the video keeps
    playing without interruption.
    """
    if not os.path.exists(video_path):
        return ""
    with open(video_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"""
<script>
(function() {{
    var doc = (window.parent || window).document;

    // ── Guard: already injected this session → do nothing ────────────────
    if (doc.getElementById('mli-bg-video')) return;

    // ── Create the video element ──────────────────────────────────────────
    var vid = doc.createElement('video');
    vid.id          = 'mli-bg-video';
    vid.autoplay    = true;
    vid.loop        = true;
    vid.muted       = true;
    vid.setAttribute('playsinline', '');
    Object.assign(vid.style, {{
        position:      'fixed',
        top:           '0',
        left:          '0',
        width:         '100vw',
        height:        '100vh',
        objectFit:     'cover',
        zIndex:        '-1',
        pointerEvents: 'none',
        opacity:       '1'
    }});

    var src  = doc.createElement('source');
    src.src  = 'data:video/mp4;base64,{encoded}';
    src.type = 'video/mp4';
    vid.appendChild(src);

    // ── Prepend to .stApp so it renders behind all Streamlit content ──────
    var host = doc.querySelector('.stApp') || doc.body;
    host.insertBefore(vid, host.firstChild);

    // Attempt autoplay (may be blocked by browser policy; fails silently)
    vid.play().catch(function() {{}});
}})();
</script>
"""


# ── 3. Page config & session-state initialisation ────────────────────────────

st.set_page_config(page_title="Fleet Optimization Simulation", layout="wide")



# ── 4. Background assets: video + animated dot canvas ────────────────────────

video_js = get_video_inject_js(VIDEO_PATH)   # <script> with inject-once guard

# Fixed dark-theme background; reduce opacity when video is present so it shows through
_BG_BASE     = '#0A0A0F'
app_bg_color = 'rgba(10, 10, 15, 0.65)' if os.path.exists(VIDEO_PATH) else _BG_BASE

# Interactive animated dot grid (mouse-reactive, rendered via canvas in the parent frame)
DOT_CANVAS_JS = """
<script>
    const parentWin = window.parent;
    const parentDoc = parentWin.document;
    const canvasId  = 'premium-dots-canvas';

    if (!parentDoc.getElementById(canvasId)) {
        const canvas = parentDoc.createElement('canvas');
        canvas.id = canvasId;
        Object.assign(canvas.style, {
            position: 'fixed', top: '0', left: '0',
            width: '100%', height: '100%',
            zIndex: '2', pointerEvents: 'none', opacity: '0.6'
        });

        const host = parentDoc.querySelector('.stApp') || parentDoc.body;
        host.appendChild(canvas);

        const ctx     = canvas.getContext('2d');
        const SPACING = 15;    // Grid spacing between dots (pixels)
        const RADIUS   = 150;  // Mouse influence radius (pixels)
        const STRENGTH = 1.5;  // Repulsion force multiplier
        const DAMPING  = 0.85; // Velocity decay per frame (0–1)
        const SPRING   = 0.05; // Spring constant pulling dots back to origin

        let width  = parentWin.innerWidth;
        let height = parentWin.innerHeight;
        let dots   = [];
        let mouseX = -1000, mouseY = -1000;

        function buildGrid() {
            canvas.width  = width;
            canvas.height = height;
            dots = [];
            for (let x = 0; x < width; x += SPACING) {
                for (let y = 0; y < height; y += SPACING) {
                    dots.push({ ox: x, oy: y, x, y, vx: 0, vy: 0 });
                }
            }
        }
        buildGrid();

        parentDoc.addEventListener('mousemove', e => { mouseX = e.clientX; mouseY = e.clientY; });
        parentWin.addEventListener('resize', () => {
            width  = parentWin.innerWidth;
            height = parentWin.innerHeight;
            buildGrid();
        });

        function animate() {
            ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';

            for (const d of dots) {
                // Mouse repulsion
                const dx   = mouseX - d.x;
                const dy   = mouseY - d.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < RADIUS) {
                    const force = (RADIUS - dist) / RADIUS;
                    const angle = Math.atan2(dy, dx);
                    d.vx -= Math.cos(angle) * force * STRENGTH;
                    d.vy -= Math.sin(angle) * force * STRENGTH;
                }
                // Spring back to origin, then dampen velocity
                d.vx += (d.ox - d.x) * SPRING;
                d.vy += (d.oy - d.y) * SPRING;
                d.vx *= DAMPING;
                d.vy *= DAMPING;
                d.x  += d.vx;
                d.y  += d.vy;

                ctx.beginPath();
                ctx.arc(d.x, d.y, 0.8, 0, Math.PI * 2);
                ctx.fill();
            }
            parentWin.requestAnimationFrame(animate);
        }
        animate();
    }
</script>
"""

# Tooltip CSS (custom HTML tooltips used in the customer insight list)
TOOLTIP_CSS = """
<style>
.tooltip {
  position: relative;
  display: inline-block;
  cursor: help;
}
.tooltip .tooltiptext {
  visibility: hidden;
  width: 240px;
  background-color: #12121a;
  color: #fff;
  text-align: left;
  border-radius: 6px;
  padding: 10px;
  position: absolute;
  z-index: 9999;
  bottom: 125%;
  left: 0;
  opacity: 0;
  transition: opacity 0.3s;
  font-size: 0.85rem;
  line-height: 1.4;
  border: 1px solid #464855;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
.tooltip:hover .tooltiptext {
  visibility: visible;
  opacity: 1;
}
</style>
"""

st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
components.html(DOT_CANVAS_JS, height=0, width=0)
if video_js:
    components.html(video_js, height=0, width=0)


# ── 5. Dynamic CSS injection ──────────────────────────────────────────────────
# Applies glassmorphism containers, theme colours, and high-contrast mode.

st.markdown(f"""
<style>
/* ── Glassmorphism containers ── */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stExpander"],
div[data-testid="stExpanderDetails"],
div[data-testid="stPopover"],
div.st-border,
div[data-testid="stContainer"] {{
    background: rgba(16, 16, 22, 1.0) !important;
    backdrop-filter: blur(30px) saturate(160%) brightness(0.95) !important;
    -webkit-backdrop-filter: blur(30px) saturate(160%) brightness(0.95) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.35) !important;
    transition: all 0.3s ease !important;
    position: relative !important;
    z-index: 10 !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover,
div[data-testid="stExpander"]:hover,
div[data-testid="stContainer"]:hover {{
    transform: translateY(-2px) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    box-shadow: 0 8px 28px rgba(0,0,0,0.45) !important;
}}

/* ── Dataframes ── */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrameGlideDataEditor"] {{
    background: rgba(16, 16, 22, 1.0) !important;
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    overflow: hidden !important;
}}

/* ── Alert / notification boxes ── */
div[data-testid="stAlert"],
div[data-testid="stNotification"],
div.stAlert,
div[role="alert"],
div[data-baseweb="notification"] {{
    backdrop-filter: blur(30px) saturate(150%) !important;
    -webkit-backdrop-filter: blur(30px) saturate(150%) !important;
    border-radius: 12px !important;
}}
div[data-testid="stInfo"],
div[data-testid="stWarning"],
div[data-testid="stSuccess"],
div[data-testid="stError"] {{
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
    border-radius: 12px !important;
}}

/* Metric cards: transparent background — styled solely by their parent container */
[data-testid="stMetric"] {{ background: transparent !important; padding: 0 !important; box-shadow: none !important; }}

/* Rounded Plotly chart wrappers */
div[data-testid="stPlotlyChart"] {{
    border-radius: 16px !important;
    overflow: hidden !important;
}}

/* ── App background ── */
[data-testid='stAppViewContainer'], .stApp, [data-testid='stHeader'] {{
    background-color: {app_bg_color} !important;
    color: #FAFAFA !important;
}}
/* Kill Streamlit default bottom padding */
.block-container {{
    padding-bottom: 0 !important;
}}
[data-testid="stAppViewContainer"] > section > div {{
    padding-bottom: 0 !important;
}}

/* iframes forward mouse events to parent for dot canvas via JS */

/* ── Sidebar: Apple-glass frosted effect ── */
[data-testid='stSidebar'] {{
    background: rgba(12, 12, 18, 0.92) !important;
    backdrop-filter: blur(50px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(50px) saturate(200%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}}

/* ── Text colours (hardcoded dark-theme defaults) ── */
h1, h2, h3, h4, h5, h6, p, span, div, label, li {{
    color: #FAFAFA !important;
}}

/* ── Accent: sliders, buttons, metric values ── */
.stSlider div[data-testid="stThumbValue"],
.stSlider div[role="slider"] {{
    background-color: #D4871C !important;
}}
div[data-testid="stMetricValue"] {{
    color: #E8993E !important;
}}
.stButton>button {{
    border-color: #D4871C !important;
    color: #E8993E !important;
}}
.stButton>button:hover {{
    background-color: #D4871C !important;
    color: #0A0A0F !important;
    border-color: #D4871C !important;
}}
.stButton>button[kind="primary"] {{
    background-color: #D4871C !important;
    color: #0A0A0F !important;
}}
</style>
""", unsafe_allow_html=True)


# ── 6. Live data pipeline ─────────────────────────────────────────────────────

# Use the Excel file's modification time as a cache key so the pipeline re-runs
# automatically whenever the source data is updated.
try:
    data_mtime = os.path.getmtime(DATA_FILE_PATH)
except FileNotFoundError:
    data_mtime = 0

@st.cache_data(show_spinner=False)
def run_cached_data_pipeline(data_mtime: float) -> bool:
    """Trigger the ETL pipeline. Re-executes only when data_mtime changes."""
    run_data_pipeline_clean()
    return True

if data_mtime:
    with st.spinner("Syncing latest live data..."):
        run_cached_data_pipeline(data_mtime)


# ── 7. Sidebar Navigation ──────────────────────────────────────────────────────

if "current_page" not in st.session_state:
    st.session_state.current_page = "systematic_concept"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('''
    <style>
    [data-testid="stSidebar"] {
        background: rgba(10, 10, 15, 0.95) !important;
        backdrop-filter: blur(30px) !important;
        -webkit-backdrop-filter: blur(30px) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: rgba(255,255,255,0.7);
    }
    /* Custom radio styling for nav tabs */
    [data-testid="stSidebar"] .stRadio > label {
        display: none !important;
    }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 4px !important;
    }
    [data-testid="stSidebar"] .stRadio > div > label {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        margin: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
        transition: all 0.25s ease !important;
        cursor: pointer !important;
    }
    [data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.06) !important;
        border-color: rgba(255,255,255,0.12) !important;
    }
    [data-testid="stSidebar"] .stRadio > div > label[data-checked="true"],
    [data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
        background: rgba(212, 135, 28, 0.12) !important;
        border-color: rgba(212, 135, 28, 0.4) !important;
        box-shadow: 0 0 20px rgba(212, 135, 28, 0.1) !important;
    }
    [data-testid="stSidebar"] .stRadio > div > label p {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    </style>
    ''', unsafe_allow_html=True)

    # Logo / Branding
    _sidebar_logo_path = os.path.join(os.path.dirname(__file__), "mobius_logo.png")
    try:
        with open(_sidebar_logo_path, "rb") as _lf:
            _sidebar_logo_b64 = base64.b64encode(_lf.read()).decode()
    except FileNotFoundError:
        _sidebar_logo_b64 = ""

    if _sidebar_logo_b64:
        st.markdown(f'''
        <div style="text-align:center;padding:16px 0 24px;">
            <img src="data:image/png;base64,{_sidebar_logo_b64}"
                 alt="Möbius AI" style="width:160px;margin-bottom:4px;" />
            <div style="font-size:0.75rem;color:rgba(255,255,255,0.35);margin-top:2px;
                        letter-spacing:1px;text-transform:uppercase;">Supply Chain Intelligence</div>
        </div>
        <div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 16px;"></div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div style="text-align:center;padding:16px 0 24px;">
            <div style="font-size:1.8rem;font-weight:800;
                        background:linear-gradient(135deg,#ffffff 0%,#a0aec0 100%);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                        letter-spacing:-0.5px;">Möbius AI</div>
            <div style="font-size:0.75rem;color:rgba(255,255,255,0.35);margin-top:2px;
                        letter-spacing:1px;text-transform:uppercase;">Supply Chain Intelligence</div>
        </div>
        <div style="height:1px;background:rgba(255,255,255,0.06);margin:0 0 16px;"></div>
        ''', unsafe_allow_html=True)

    _nav_options = [
        "Systematic Concept",
        "Control Tower",
        "Tracking Return Status",
        "Real World Simulation",
        "Fleet Optimization",
    ]
    _nav_map = {
        "Systematic Concept": "systematic_concept",
        "Control Tower": "control_tower",
        "Tracking Return Status": "tracking",
        "Real World Simulation": "real_world_sim",
        "Fleet Optimization": "simulation",
    }
    _reverse_map = {v: k for k, v in _nav_map.items()}

    _current_label = _reverse_map.get(st.session_state.current_page, _nav_options[0])

    _selected = st.radio(
        "Navigation",
        _nav_options,
        index=_nav_options.index(_current_label),
        key="nav_radio",
    )

    _new_page = _nav_map[_selected]
    if _new_page != st.session_state.current_page:
        st.session_state.current_page = _new_page
        st.rerun()




# ── Page dispatch — each page is a separate module in modules/ ────────────────

if st.session_state.current_page == "systematic_concept":
    from modules.systematic_concept import render as render_sc
    render_sc()

elif st.session_state.current_page == "control_tower":
    from modules.control_tower import render as render_ct
    render_ct()

elif st.session_state.current_page == "real_world_sim":
    from modules.real_world_sim import render as render_rw
    render_rw()

elif st.session_state.current_page == "tracking":
    from modules.tracking import render as render_trk
    render_trk()

elif st.session_state.current_page == "simulation":
    from modules.fleet_optimization import render as render_fleet
    render_fleet()

else:
    from modules.control_tower import render as render_ct_fallback
    render_ct_fallback()

# ── Global footer ─────────────────────────────────────────────────────────────
st.markdown('''
<div style="margin-top:40px;padding-top:30px;border-top:1px solid rgba(255,255,255,0.08);">
  <div style="display:flex;justify-content:center;align-items:stretch;max-width:750px;margin:0 auto;">
    <div style="flex:1;display:flex;align-items:center;justify-content:center;
                padding:16px 24px;border-right:1px solid rgba(255,255,255,0.15);">
      <div style="text-align:center;">
        <p style="margin:0 0 8px;font-size:14px;font-weight:600;color:rgba(255,255,255,0.85);font-style:italic;">
          Arizona State University — W. P. Carey School of Business</p>
        <p style="margin:0 0 4px;font-size:12px;color:rgba(255,255,255,0.45);font-style:italic;">
          2026 Master of Supply Chain Management</p>
        <p style="margin:0 0 4px;font-size:12px;color:rgba(255,255,255,0.45);font-style:italic;">
          Project Professors: <a href="https://search.asu.edu/profile/5120930" target="_blank" style="color:inherit;text-decoration:none;">Parag Dhumal</a>, <a href="https://search.asu.edu/profile/268915" target="_blank" style="color:inherit;text-decoration:none;">Tracey Lauterborn</a></p>
        <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.45);font-style:italic;">
          Capstone Project — Team Maroon 5</p>
      </div>
    </div>
    <div style="flex:1;display:flex;align-items:center;padding:16px 24px;">
      <table style="border-collapse:separate;border-spacing:0 4px;font-size:12px;">
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Project Executor</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;"><a href="https://www.linkedin.com/in/hung-ting-lin-42071b344/" target="_blank" style="color:#D4871C;text-decoration:none;">Jarvis Lin</a></td></tr>
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Systematic Engineer</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;"><a href="https://www.linkedin.com/in/hung-ting-lin-42071b344/" target="_blank" style="color:#D4871C;text-decoration:none;">Jarvis Lin</a></td></tr>
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Project Manager</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;">Ali Assiri</td></tr>
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Project Planner</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;">Meshari Alalyani</td></tr>
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Data Analyst, Coordinator</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;">Yifan Liu</td></tr>
        <tr><td style="padding:5px 12px;color:rgba(255,255,255,0.55);border:none;">Data Validator</td><td style="padding:5px 12px;color:#D4871C;font-weight:600;border:none;">Hassan Al Murdhimah</td></tr>
      </table>
    </div>
  </div>
</div>
''', unsafe_allow_html=True)


try:
    import base64 as _b64
    _footer_logo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'footer_logos.png'
    )
    if os.path.exists(_footer_logo_path):
        @st.cache_data(show_spinner=False)
        def _load_global_footer_logo(path: str) -> str:
            with open(path, 'rb') as f:
                return _b64.b64encode(f.read()).decode()
        _fl_b64 = _load_global_footer_logo(_footer_logo_path)
        _, _fc, _ = st.columns([2, 5, 2])
        with _fc:
            st.markdown(
                f'<div style="text-align:center;margin-top:20px;">'
                f'<img src="data:image/png;base64,{_fl_b64}" '
                f'style="max-width:605px;width:100%;display:block;margin:0 auto;opacity:0.85;"></div>',
                unsafe_allow_html=True
            )
except Exception:
    pass

# ── Global Möbius AI Intelligence Panel (available on every page) ─────────────
from modules.mobius_ai import render as render_ai
render_ai()

# ── Global footer CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
section[data-testid="stBottom"],
footer { background: transparent !important; box-shadow: none !important; }

[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button,
[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button:hover,
[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button:focus,
[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button:active {
    border: none !important;
    border-color: transparent !important;
    outline: none !important;
    background: transparent !important;
    box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)

