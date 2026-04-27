"""
modules/systematic_concept.py
------------------------------
The Systematic Concept — Visual data pipeline & architecture flowchart.

Renders a full-page interactive flowchart showing every stage of the
Möbius AI system: from the raw Excel workbook through ETL, imputation,
sync engines, JSON artifact generation, to the four dashboard pages
and the AI intelligence layer.

Uses streamlit.components.v1.html() for full CSS/HTML rendering support.
"""
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components


def render():
    """Render the Systematic Concept flowchart page."""

    # ── Page header (rendered by Streamlit natively) ──────────────────────
    st.markdown('''
    <div style="margin-bottom:28px;">
        <h1 style="font-size:2.4rem;font-weight:800;margin:0 0 4px;
                   background:linear-gradient(135deg,#ffffff 0%,#a0aec0 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            🔬 The Systematic Concept
        </h1>
        <p style="color:#8892b0;font-size:1rem;margin:0;">
            End-to-end data pipeline architecture — How raw data becomes actionable intelligence
        </p>
    </div>
    ''', unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚠️ Problem Statement",
        "📐 System Architecture",
        "🔄 Data Pipeline Flow",
        "🚀 Tech Stack",
    ])

    with tab1:
        problems_html = _build_problems_html()
        components.html(problems_html, height=750, scrolling=False)

    with tab2:
        flowchart_html = _build_flowchart_html()
        components.html(flowchart_html, height=4330, scrolling=False)

    with tab3:
        pipeline_html = _build_pipeline_flow_html()
        components.html(pipeline_html, height=2500, scrolling=False)

    with tab4:
        cicd_html = _build_cicd_html()
        components.html(cicd_html, height=1150, scrolling=False)


def _build_flowchart_html() -> str:
    """Build the complete self-contained HTML page for the flowchart."""
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: transparent;
    color: white;
    padding: 10px 20px 40px;
}

/* ── Container ── */
.fc { max-width: 1050px; margin: 0 auto; }

/* ── Phase label ── */
.phase {
    display: flex; align-items: center; gap: 12px;
    width: 100%;
    background: linear-gradient(135deg, rgba(20,22,30,0.9) 0%, rgba(30,34,44,0.85) 100%);
    background-image:
        radial-gradient(rgba(255,255,255,0.04) 1px, transparent 1px);
    background-size: 16px 16px;
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 4px solid currentColor;
    border-radius: 14px;
    padding: 18px 28px;
    font-size: 1.05rem; font-weight: 800; letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 18px;
    margin-top: 8px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    /* Start state: slightly zoomed in + dim */
    transform: scale(0.94);
    opacity: 0.4;
    filter: brightness(0.6);
}
.phase.in-view {
    transform: scale(1);
    opacity: 1;
    filter: brightness(1.1);
    box-shadow: 0 6px 36px rgba(0,0,0,0.4), 0 0 20px rgba(212,135,28,0.08);
}
.phase:hover {
    border-left-width: 6px;
    box-shadow: 0 6px 32px rgba(0,0,0,0.45);
    transform: scale(1.02) translateX(2px);
    filter: brightness(1.2);
}

/* ── Nodes ── */
.node {
    background: rgba(30,32,40,0.75); backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 14px;
    padding: 16px 20px; text-align: center;
    transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    cursor: default;
}
.node:hover {
    transform: scale(1.08) translateY(-4px);
    border-color: rgba(212,135,28,0.3);
    box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 16px rgba(212,135,28,0.1);
    filter: brightness(1.15);
    z-index: 10;
}
.icon { font-size: 1.5rem; margin-bottom: 6px; }
.title { font-size: 0.88rem; font-weight: 700; color: white; margin-bottom: 4px; }
.desc { font-size: 0.67rem; color: rgba(255,255,255,0.45); line-height: 1.45; }

/* ── Start/end ── */
.start {
    background: linear-gradient(135deg, rgba(0,82,204,0.25), rgba(56,189,248,0.15));
    border: 2px solid #0052cc; border-radius: 50px; padding: 20px 32px;
}
.end {
    background: linear-gradient(135deg, rgba(34,197,94,0.2), rgba(56,189,248,0.1));
    border: 2px solid #22c55e; border-radius: 50px; padding: 18px 28px;
}

/* ── Arrow ── */
.arrow { display: flex; justify-content: center; padding: 4px 0; }
.arrow-line {
    width: 3px; height: 36px; position: relative;
    background: linear-gradient(to bottom, rgba(255,255,255,0.18), rgba(255,255,255,0.06));
    border-radius: 2px;
    overflow: hidden;
}
.arrow-line::before {
    content: '';
    position: absolute; top: -10px; left: -1px;
    width: 5px; height: 10px;
    border-radius: 3px;
    background: rgba(212,135,28,0.8);
    box-shadow: 0 0 6px rgba(212,135,28,0.5);
    animation: dot-flow 1.4s linear infinite;
}
@keyframes dot-flow {
    0%   { top: -10px; opacity: 0; }
    15%  { opacity: 1; }
    85%  { opacity: 1; }
    100% { top: 36px; opacity: 0; }
}
.arrow-line::after {
    content: ''; position: absolute; bottom: -6px; left: 50%;
    transform: translateX(-50%);
    border-left: 6px solid transparent; border-right: 6px solid transparent;
    border-top: 8px solid rgba(255,255,255,0.18);
}
.arrow-s .arrow-line { height: 22px; }
.arrow-s .arrow-line::before { animation-duration: 1s; }

/* ── Row ── */
.row { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.row > .node { flex: 1; min-width: 130px; max-width: 220px; }

/* ── Decision diamond ── */
.diamond-wrap { display: flex; justify-content: center; padding: 20px 0 12px; }
.diamond {
    width: 170px; height: 170px; transform: rotate(45deg);
    display: flex; align-items: center; justify-content: center;
    border-radius: 14px; transition: all 0.3s;
}
.diamond:hover { box-shadow: 0 0 30px rgba(250,204,21,0.2); }
.diamond-in {
    transform: rotate(-45deg); text-align: center; padding: 6px;
}
.diamond-in .icon { font-size: 1.1rem; margin-bottom: 2px; }
.diamond-in .title { font-size: 0.74rem; }

/* ── Branch ── */
.branch { display: flex; justify-content: center; gap: 40px; align-items: flex-start; }
.arm { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.label-yes {
    font-size: 0.75rem; font-weight: 700; padding: 3px 14px; border-radius: 12px;
    background: rgba(34,197,94,0.15); color: #22c55e; border: 1px solid rgba(34,197,94,0.3);
}
.label-no {
    font-size: 0.75rem; font-weight: 700; padding: 3px 14px; border-radius: 12px;
    background: rgba(239,68,68,0.12); color: #ef4444; border: 1px solid rgba(239,68,68,0.25);
}

/* ── File badges ── */
.files { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin: 8px 0; }
.file {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 6px 12px;
    font-size: 0.64rem; font-weight: 600; color: rgba(255,255,255,0.6);
    font-family: 'Courier New', monospace;
}

/* ── Color accents ── */
.bl { border-left: 4px solid #38bdf8; }
.gr { border-left: 4px solid #22c55e; }
.pu { border-left: 4px solid #a78bfa; }
.yl { border-left: 4px solid #facc15; }
.or { border-left: 4px solid #ff8c42; }
.pk { border-left: 4px solid #f472b6; }

/* ── Sub-boxes ── */
.sub {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px; padding: 10px 14px; text-align: left; flex: 1; min-width: 190px;
}
.sub-title { font-size: 0.72rem; font-weight: 700; margin-bottom: 4px; }
.sub-desc { font-size: 0.61rem; color: rgba(255,255,255,0.5); line-height: 1.5; }

/* ── Tag pills ── */
.tag {
    display: inline-block; padding: 5px 12px; border-radius: 8px;
    font-size: 0.65rem; font-weight: 600;
}
.pill { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.6rem; font-weight: 700; }

/* ── Centered wrapper ── */
.center { display: flex; justify-content: center; }
</style>
</head>
<body>
<div class="fc">

<!-- ═══ PHASE 1: DATA SOURCE ═══ -->
<div class="phase" style="color:#38bdf8;">📥 Phase 1 — Data Source</div>
<div class="center">
    <div class="node start" style="max-width:520px;width:100%;">
        <div class="icon">📊</div>
        <div class="title" style="font-size:1.05rem;">MLI Capstone Data.xlsx</div>
        <div class="desc">Single Excel workbook — the master data source for the entire system</div>
        <div class="files" style="margin-top:10px;">
            <div class="file" style="color:#38bdf8;">📋 Sales QTY</div>
            <div class="file" style="color:#22c55e;">🏭 MFG Date</div>
            <div class="file" style="color:#a78bfa;">⏱ Loop Times</div>
            <div class="file" style="color:#facc15;">♻️ R2R Data</div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 2: CLEANING ═══ -->
<div class="phase" style="color:#22c55e;">🧹 Phase 2 — Sheet-Level Cleaning (data_cleaner.py)</div>
<div class="row">
    <div class="node bl">
        <div class="icon">📋</div>
        <div class="title">Clean Sales QTY</div>
        <div class="desc">Remove Grand Total rows, parse dates, forward-fill customer labels</div>
    </div>
    <div class="node gr">
        <div class="icon">🏭</div>
        <div class="title">Clean MFG Date</div>
        <div class="desc">Convert dates to datetime, nullify Excel epoch (1899-12-31)</div>
    </div>
    <div class="node pu">
        <div class="icon">⏱</div>
        <div class="title">Clean Loop Times</div>
        <div class="desc">Strip whitespace from column names to prevent mismatches</div>
    </div>
    <div class="node yl">
        <div class="icon">♻️</div>
        <div class="title">Clean R2R Data</div>
        <div class="desc">Fill missing R2R median values with column mean</div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<div class="files">
    <div class="file" style="border-left:3px solid #38bdf8;">CLEANED_Sales_QTY.csv</div>
    <div class="file" style="border-left:3px solid #22c55e;">CLEANED_MFG_Date.csv</div>
    <div class="file" style="border-left:3px solid #a78bfa;">CLEANED_Loop_Times.csv</div>
    <div class="file" style="border-left:3px solid #facc15;">CLEANED_R2R_Data.csv</div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 3: IMPUTATION ═══ -->
<div class="phase" style="color:#a78bfa;">🧬 Phase 3 — Two-Phase Imputation (data_imputer.py)</div>
<div class="center">
    <div class="node pu" style="max-width:660px;width:100%;">
        <div class="icon">🧬</div>
        <div class="title">Two-Phase Imputation Engine</div>
        <div style="display:flex;gap:14px;margin-top:10px;justify-content:center;flex-wrap:wrap;">
            <div class="sub" style="border-color:rgba(167,139,250,0.25);">
                <div class="sub-title" style="color:#a78bfa;">Phase 1: Null-Fill</div>
                <div class="sub-desc">
                    • Poisson-distributed quantity fills<br>
                    • Median + stochastic noise for transit<br>
                    • Random MFG dates (2018–2023)
                </div>
            </div>
            <div class="sub" style="border-color:rgba(250,204,21,0.2);">
                <div class="sub-title" style="color:#facc15;">Phase 2: Zero Replacement</div>
                <div class="sub-desc">
                    • Tier 1: Customer-level mean<br>
                    • Tier 2: Container-type mean<br>
                    • Tier 3: Global column mean
                </div>
            </div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<div class="files">
    <div class="file" style="border-left:3px solid #22c55e;color:#22c55e;">FINAL_Sales_QTY.csv</div>
    <div class="file" style="border-left:3px solid #22c55e;color:#22c55e;">FINAL_MFG_Date.csv</div>
    <div class="file" style="border-left:3px solid #22c55e;color:#22c55e;">FINAL_Loop_Times.csv</div>
    <div class="file" style="border-left:3px solid #22c55e;color:#22c55e;">FINAL_R2R_Data.csv</div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 4: DECISION — MISSING MFG? ═══ -->
<div class="phase" style="color:#ff8c42;">🏭 Phase 4 — MFG Data Sync (mfg_generator.py)</div>
<div class="diamond-wrap">
    <div class="diamond" style="background:rgba(255,140,66,0.1);border:2px solid rgba(255,140,66,0.4);">
        <div class="diamond-in">
            <div class="icon">❓</div>
            <div class="title" style="color:#ff8c42;">Products in<br>Sales missing<br>from MFG?</div>
        </div>
    </div>
</div>
<div class="branch">
    <div class="arm">
        <div class="label-yes">✅ YES</div>
        <div class="arrow arrow-s"><div class="arrow-line"></div></div>
        <div class="node or" style="max-width:280px;">
            <div class="icon">🏭</div>
            <div class="title">MFG Generator</div>
            <div class="desc">Auto-generate serial numbers, MFG dates, fleet records. 60% Green / 40% Amber age profile</div>
        </div>
        <div style="font-size:0.58rem;color:rgba(255,255,255,0.3);">↓ Merge into FINAL_MFG_Date.csv</div>
    </div>
    <div class="arm">
        <div class="label-no">❌ NO</div>
        <div style="height:50px;display:flex;align-items:center;">
            <div style="font-size:0.62rem;color:rgba(255,255,255,0.3);font-style:italic;">Skip — continue ↓</div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 5: JSON GENERATION ═══ -->
<div class="phase" style="color:#f472b6;">📦 Phase 5 — Artifact Generation</div>
<div class="row" style="max-width:660px;margin:0 auto;">
    <div class="node pk" style="flex:1;">
        <div class="icon">📊</div>
        <div class="title" style="font-family:'Courier New',monospace;font-size:0.8rem;">item_metrics.json</div>
        <div class="desc">Per-product: daily demand, dwell mean, fleet size, asset age list</div>
    </div>
    <div class="node pk" style="flex:1;">
        <div class="icon">👥</div>
        <div class="title" style="font-family:'Courier New',monospace;font-size:0.8rem;">customer_insights.json</div>
        <div class="desc">Per-customer: order history, frequency, anomalies (Z&gt;2.0), contracted dwell</div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 6: DECISION — DATE GAP? ═══ -->
<div class="phase" style="color:#facc15;">🔄 Phase 6 — Live Sync Engines</div>
<div class="diamond-wrap">
    <div class="diamond" style="background:rgba(250,204,21,0.08);border:2px solid rgba(250,204,21,0.35);">
        <div class="diamond-in">
            <div class="icon">📅</div>
            <div class="title" style="color:#facc15;">Today &gt; last<br>recorded<br>sale date?</div>
        </div>
    </div>
</div>
<div class="branch">
    <div class="arm">
        <div class="label-yes">✅ YES</div>
        <div class="arrow arrow-s"><div class="arrow-line"></div></div>
        <div class="node yl" style="max-width:300px;">
            <div class="icon">📈</div>
            <div class="title">EWMA Gap Filler</div>
            <div class="desc">Generate synthetic orders using EWMA momentum (span=30) + Gaussian noise → append to FINAL_Sales_QTY.csv</div>
        </div>
    </div>
    <div class="arm">
        <div class="label-no">❌ NO</div>
        <div style="height:50px;display:flex;align-items:center;">
            <div style="font-size:0.62rem;color:rgba(255,255,255,0.3);font-style:italic;">Already synced ↓</div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 7: RETURN TRACKER ═══ -->
<div class="phase" style="color:#a78bfa;">📍 Phase 7 — Asset Position Engine (return_tracker.py)</div>
<div class="center">
    <div class="node pu" style="max-width:700px;width:100%;">
        <div class="icon">📍</div>
        <div class="title">Return Tracker — Live Twin Engine</div>
        <div class="desc" style="margin-bottom:10px;">Assigns loop position to every serialized container based on shipment dates + documented loop times</div>
        <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
            <div class="tag" style="background:rgba(34,197,94,0.12);color:#22c55e;border:1px solid rgba(34,197,94,0.25);">✅ Available at MLI</div>
            <div class="tag" style="background:rgba(255,140,66,0.12);color:#ff8c42;border:1px solid rgba(255,140,66,0.25);">🚛 Transit → Customer</div>
            <div class="tag" style="background:rgba(250,204,21,0.1);color:#facc15;border:1px solid rgba(250,204,21,0.2);">📦 At Customer Site</div>
            <div class="tag" style="background:rgba(167,139,250,0.12);color:#a78bfa;border:1px solid rgba(167,139,250,0.25);">🔄 Returning → MLI</div>
        </div>
        <div style="margin-top:10px;font-size:0.6rem;color:rgba(255,255,255,0.35);">
            + EU Compliance: 🟢 Green (&lt; 4.25 years) vs 🟡 Amber (&gt; 4.25 years)
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 8: DASHBOARD ═══ -->
<div class="phase" style="color:#0052cc;">🖥️ Phase 8 — Dashboard Rendering (app.py → Streamlit)</div>
<div class="center" style="margin-bottom:14px;">
    <div class="node" style="max-width:400px;width:100%;border:2px solid rgba(0,82,204,0.4);
                background:linear-gradient(135deg,rgba(0,82,204,0.12),rgba(56,189,248,0.06));">
        <div class="icon">🖥️</div>
        <div class="title" style="font-size:1rem;">Streamlit Dashboard (app.py)</div>
        <div class="desc">Global shell: page config, glassmorphism CSS, video background, animated dot canvas, sidebar navigation</div>
    </div>
</div>
<div class="arrow arrow-s"><div class="arrow-line"></div></div>
<div class="row" style="margin-top:6px;">
    <div class="node" style="border-top:3px solid #38bdf8;">
        <div class="icon">🏢</div>
        <div class="title" style="color:#38bdf8;">Control Tower</div>
        <div class="desc">
            Executive KPIs<br>Fleet Health Snapshot<br>Risk Alert Engine<br>Multi-Agent War Room<br>
            <span style="font-size:0.55rem;color:rgba(56,189,248,0.6);">4 AI agents via Gemini</span>
        </div>
    </div>
    <div class="node" style="border-top:3px solid #facc15;">
        <div class="icon">💰</div>
        <div class="title" style="color:#facc15;">Real World Sim</div>
        <div class="desc">
            What-If Simulator<br>EWMA Forecast Charts<br>Sankey Asset Flow<br>Optimal Fleet Sizing<br>
            <span style="font-size:0.55rem;color:rgba(250,204,21,0.6);">Demand surge + delay</span>
        </div>
    </div>
    <div class="node" style="border-top:3px solid #a78bfa;">
        <div class="icon">📦</div>
        <div class="title" style="color:#a78bfa;">Tracking Status</div>
        <div class="desc">
            Serial Registry<br>Loop Journey Pipeline<br>Age/Status Charts<br>Co-shipped Containers<br>
            <span style="font-size:0.55rem;color:rgba(167,139,250,0.6);">4-stage pipeline per asset</span>
        </div>
    </div>
    <div class="node" style="border-top:3px solid #22c55e;">
        <div class="icon">🌍</div>
        <div class="title" style="color:#22c55e;">Fleet Optimization</div>
        <div class="desc">
            Monte Carlo Sim<br>Customer Tiering<br>Cross-Product Scoring<br>Customer Deep Dive<br>
            <span style="font-size:0.55rem;color:rgba(34,197,94,0.6);">Binary search → optimal</span>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 9: AI LAYER ═══ -->
<div class="phase" style="color:#f472b6;">🤖 Phase 9 — AI Intelligence Layer</div>
<div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap;max-width:850px;margin:0 auto;">
    <div class="node pk" style="flex:1;min-width:200px;">
        <div class="icon">🧠</div>
        <div class="title">AI Context Builder</div>
        <div class="desc">Compiles full database snapshot: customers, histories, contracts, R2R, anomalies → JSON</div>
    </div>
    <div style="display:flex;align-items:center;font-size:1.2rem;color:rgba(255,255,255,0.2);">→</div>
    <div class="node pk" style="flex:1;min-width:200px;">
        <div class="icon">🤖</div>
        <div class="title">Möbius AI Chat</div>
        <div class="desc">Gemini API powered. Image/file attachments. Persistent chat sessions. All pages</div>
    </div>
    <div style="display:flex;align-items:center;font-size:1.2rem;color:rgba(255,255,255,0.2);">→</div>
    <div class="node pk" style="flex:1;min-width:200px;">
        <div class="icon">📋</div>
        <div class="title">Anomaly Archive</div>
        <div class="desc">Persistent JSON log of analyst-classified demand anomalies with Z-scores & notes</div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 10: SIMULATION ENGINE ═══ -->
<div class="phase" style="color:#ff8c42;">⚙️ Phase 10 — Monte Carlo Simulation (fleet_sim.py)</div>
<div class="center">
    <div class="node or" style="max-width:750px;width:100%;">
        <div class="icon">⚙️</div>
        <div class="title" style="font-size:0.95rem;">Discrete-Event Asset Lifecycle Simulation</div>
        <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin:14px 0;flex-wrap:wrap;">
            <div class="tag" style="background:rgba(34,197,94,0.12);color:#22c55e;border:1px solid rgba(34,197,94,0.25);">🏭 Warehouse</div>
            <span style="color:rgba(255,255,255,0.2);">→</span>
            <div class="tag" style="background:rgba(255,140,66,0.12);color:#ff8c42;border:1px solid rgba(255,140,66,0.25);">🚛 Transit Out<br><span style="font-size:0.5rem;opacity:0.6;">2-5 days</span></div>
            <span style="color:rgba(255,255,255,0.2);">→</span>
            <div class="tag" style="background:rgba(250,204,21,0.1);color:#facc15;border:1px solid rgba(250,204,21,0.2);">📦 Customer<br><span style="font-size:0.5rem;opacity:0.6;">dwell ± 3d σ</span></div>
            <span style="color:rgba(255,255,255,0.2);">→</span>
            <div class="tag" style="background:rgba(167,139,250,0.12);color:#a78bfa;border:1px solid rgba(167,139,250,0.25);">🔄 Transit In<br><span style="font-size:0.5rem;opacity:0.6;">2-5 days</span></div>
            <span style="color:rgba(255,255,255,0.2);">→</span>
            <div class="tag" style="background:rgba(56,189,248,0.12);color:#38bdf8;border:1px solid rgba(56,189,248,0.25);">🔧 Maintenance<br><span style="font-size:0.5rem;opacity:0.6;">1-3 days</span></div>
            <span style="color:rgba(255,255,255,0.2);">→</span>
            <div class="tag" style="background:rgba(34,197,94,0.12);color:#22c55e;border:1px solid rgba(34,197,94,0.25);">🏭 Warehouse</div>
        </div>
        <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
            <div class="pill" style="color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.04);">📆 365-day simulation</div>
            <div class="pill" style="color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.04);">🔥 100-day warm-up</div>
            <div class="pill" style="color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.04);">📉 0.3% loss rate/trip</div>
            <div class="pill" style="color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.04);">🇪🇺 4.25yr EU retirement</div>
            <div class="pill" style="color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.04);">🔍 Binary search optimization</div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ PHASE 11: TIERING ═══ -->
<div class="phase" style="color:#22c55e;">🎯 Phase 11 — Strategic Customer Tiering</div>
<div class="center">
    <div class="node gr" style="max-width:700px;width:100%;">
        <div class="icon">🎯</div>
        <div class="title">Weighted Composite Score (0–100)</div>
        <div style="display:flex;gap:8px;justify-content:center;margin:12px 0;flex-wrap:wrap;">
            <div class="tag" style="background:rgba(250,204,21,0.1);border:1px solid rgba(250,204,21,0.25);text-align:center;">
                <div style="font-size:1.1rem;font-weight:800;color:#facc15;">35%</div>
                <div style="font-size:0.58rem;color:rgba(255,255,255,0.5);">Volume Rank</div>
            </div>
            <div class="tag" style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.2);text-align:center;">
                <div style="font-size:1.1rem;font-weight:800;color:#22c55e;">25%</div>
                <div style="font-size:0.58rem;color:rgba(255,255,255,0.5);">Consistency</div>
            </div>
            <div class="tag" style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);text-align:center;">
                <div style="font-size:1.1rem;font-weight:800;color:#ef4444;">20%</div>
                <div style="font-size:0.58rem;color:rgba(255,255,255,0.5);">Anomaly Density</div>
            </div>
            <div class="tag" style="background:rgba(167,139,250,0.1);border:1px solid rgba(167,139,250,0.2);text-align:center;">
                <div style="font-size:1.1rem;font-weight:800;color:#a78bfa;">20%</div>
                <div style="font-size:0.58rem;color:rgba(255,255,255,0.5);">Contract Adherence</div>
            </div>
        </div>
        <div style="display:flex;gap:6px;justify-content:center;flex-wrap:wrap;">
            <div class="pill" style="background:rgba(34,197,94,0.15);color:#22c55e;">🏆 Strategic ≥ 75</div>
            <div class="pill" style="background:rgba(56,189,248,0.12);color:#38bdf8;">📈 Growth ≥ 55</div>
            <div class="pill" style="background:rgba(167,139,250,0.12);color:#a78bfa;">📊 Maintain ≥ 35</div>
            <div class="pill" style="background:rgba(250,204,21,0.1);color:#facc15;">👁️ Monitor ≥ 18</div>
            <div class="pill" style="background:rgba(239,68,68,0.1);color:#ef4444;">⚠️ Deprioritize &lt; 18</div>
        </div>
    </div>
</div>

<div class="arrow"><div class="arrow-line"></div></div>

<!-- ═══ END ═══ -->
<div class="center">
    <div class="node end" style="max-width:480px;width:100%;">
        <div class="icon">🚀</div>
        <div class="title" style="font-size:1rem;">Live Dashboard → User Browser</div>
        <div class="desc">
            localhost:8501 — Auto-refreshing, cache-invalidated pipeline<br>
            <span style="color:rgba(34,197,94,0.7);">Data updates trigger full re-computation automatically</span>
        </div>
    </div>
</div>

</div><!-- /fc -->
<script>
// Scroll-triggered phase reveal
const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
        if (e.isIntersecting) e.target.classList.add('in-view');
    });
}, { threshold: 0.3 });
document.querySelectorAll('.phase').forEach(el => observer.observe(el));

// Forward mouse events to parent for background dot animation
document.addEventListener('mousemove', e => {
    const iframe = window.frameElement;
    if (iframe) {
        const rect = iframe.getBoundingClientRect();
        const evt = new MouseEvent('mousemove', {
            clientX: rect.left + e.clientX,
            clientY: rect.top + e.clientY
        });
        window.parent.document.dispatchEvent(evt);
    }
});
</script>
</body>
</html>
'''


def _build_pipeline_flow_html() -> str:
    """Build an interactive data pipeline flow visualization showing actual project files."""
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: transparent;
    color: white;
    padding: 10px 20px 40px;
}

.pipeline { max-width: 1100px; margin: 0 auto; }

/* ── Layer label ── */
.layer {
    display: flex; align-items: center; gap: 14px;
    width: 100%;
    background: linear-gradient(135deg, rgba(20,22,30,0.9) 0%, rgba(30,34,44,0.85) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 4px solid;
    border-radius: 14px;
    padding: 16px 28px;
    font-size: 0.95rem; font-weight: 800; letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 16px; margin-top: 20px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    transition: all 0.3s ease;
}
.layer:hover {
    border-left-width: 6px;
    transform: translateX(2px);
    box-shadow: 0 6px 32px rgba(0,0,0,0.45);
}

/* ── File nodes ── */
.file-row {
    display: flex; gap: 14px; justify-content: center;
    flex-wrap: wrap; margin-bottom: 8px;
}
.file-node {
    background: rgba(30,32,40,0.75); backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 14px;
    padding: 18px 22px; text-align: center;
    min-width: 180px; max-width: 240px; flex: 1;
    transition: all 0.35s ease;
    position: relative;
    overflow: hidden;
}
.file-node::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    border-radius: 14px 14px 0 0;
    transition: height 0.3s ease;
}
.file-node:hover {
    transform: translateY(-4px); border-color: rgba(255,255,255,0.22);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.file-node:hover::before { height: 5px; }
.file-icon { font-size: 1.6rem; margin-bottom: 8px; }
.file-name {
    font-size: 0.82rem; font-weight: 700; color: white;
    margin-bottom: 4px; font-family: "SF Mono", "Fira Code", monospace;
}
.file-desc { font-size: 0.68rem; color: rgba(255,255,255,0.45); line-height: 1.5; }
.file-output {
    margin-top: 8px; padding-top: 8px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.output-tag {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; padding: 2px 8px;
    font-size: 0.62rem; font-family: "SF Mono", monospace;
    color: rgba(255,255,255,0.55); margin: 2px;
}

/* ── Flow arrows ── */
.flow-arrow {
    text-align: center; margin: 6px 0 8px;
    font-size: 1.2rem; color: rgba(255,255,255,0.2);
    animation: pulse-arrow 2s ease-in-out infinite;
}
@keyframes pulse-arrow {
    0%, 100% { opacity: 0.2; transform: translateY(0); }
    50% { opacity: 0.5; transform: translateY(3px); }
}

/* ── Color themes per layer ── */
.layer-source { border-left-color: #D4871C; color: #D4871C; }
.node-source::before { background: linear-gradient(90deg, #D4871C, #E8993E); }

.layer-clean { border-left-color: #22C55E; color: #22C55E; }
.node-clean::before { background: linear-gradient(90deg, #22C55E, #4ADE80); }

.layer-impute { border-left-color: #3B82F6; color: #3B82F6; }
.node-impute::before { background: linear-gradient(90deg, #3B82F6, #60A5FA); }

.layer-engine { border-left-color: #A855F7; color: #A855F7; }
.node-engine::before { background: linear-gradient(90deg, #A855F7, #C084FC); }

.layer-artifact { border-left-color: #F59E0B; color: #F59E0B; }
.node-artifact::before { background: linear-gradient(90deg, #F59E0B, #FBBF24); }

.layer-dash { border-left-color: #06B6D4; color: #06B6D4; }
.node-dash::before { background: linear-gradient(90deg, #06B6D4, #22D3EE); }

/* ── Animated data particles ── */
.flow-line {
    text-align: center; margin: 4px 0;
    position: relative; height: 36px;
    display: flex; align-items: center; justify-content: center;
}
.flow-line svg { width: 4px; height: 36px; }
.flow-line .dot-track {
    width: 2px; height: 36px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    position: relative; overflow: hidden;
}
.flow-line .dot-track::after {
    content: '';
    position: absolute; top: -8px; left: -1px;
    width: 4px; height: 8px;
    border-radius: 4px;
    background: currentColor;
    animation: data-flow 1.5s linear infinite;
}
@keyframes data-flow {
    0% { top: -8px; opacity: 0; }
    20% { opacity: 1; }
    80% { opacity: 1; }
    100% { top: 36px; opacity: 0; }
}

.flow-line.color-source .dot-track { color: #D4871C; }
.flow-line.color-clean .dot-track { color: #22C55E; }
.flow-line.color-impute .dot-track { color: #3B82F6; }
.flow-line.color-engine .dot-track { color: #A855F7; }
.flow-line.color-artifact .dot-track { color: #F59E0B; }

/* ── Wide single node ── */
.file-node.wide { max-width: 480px; min-width: 300px; }

/* ── Multi-arrow row ── */
.multi-arrow {
    display: flex; justify-content: center; gap: 140px;
    margin: 4px 0;
}

</style>
</head>
<body>
<div class="pipeline">

<!-- ═══════════════════════ LAYER 1: DATA SOURCE ═══════════════════════ -->
<div class="layer layer-source">📁 Layer 1 — Data Source</div>
<div class="file-row">
    <div class="file-node node-source wide">
        <div class="file-icon">📊</div>
        <div class="file-name">MLI Capstone Data.xlsx</div>
        <div class="file-desc">
            Master Excel workbook — single source of truth<br>
            Contains all raw operational data
        </div>
        <div class="file-output">
            <span class="output-tag">Sales QTY</span>
            <span class="output-tag">MFG Date</span>
            <span class="output-tag">Loop Times</span>
            <span class="output-tag">R2R Data</span>
            <span class="output-tag">Contracts</span>
        </div>
    </div>
</div>

<div class="flow-line color-source"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 2: CLEANING ═══════════════════════ -->
<div class="layer layer-clean">🧹 Layer 2 — Sheet-Level Cleaning</div>
<div class="file-row">
    <div class="file-node node-clean">
        <div class="file-icon">🧬</div>
        <div class="file-name">data_cleaner.py</div>
        <div class="file-desc">
            ETL pipeline — reads each Excel sheet,<br>
            removes totals, forward-fills headers,<br>
            normalizes dates & types
        </div>
        <div class="file-output">
            <span class="output-tag">CLEANED_Sales_QTY.csv</span>
            <span class="output-tag">CLEANED_MFG_Date.csv</span>
            <span class="output-tag">CLEANED_Documented_Loop_Times.csv</span>
            <span class="output-tag">CLEANED_Receipt_to_Receipt_Data.csv</span>
        </div>
    </div>
    <div class="file-node node-clean">
        <div class="file-icon">⚙️</div>
        <div class="file-name">config.py</div>
        <div class="file-desc">
            Central configuration —<br>
            all file paths, sheet names,<br>
            and shared constants
        </div>
        <div class="file-output">
            <span class="output-tag">BASE_DIR</span>
            <span class="output-tag">DATA_FILE_PATH</span>
            <span class="output-tag">SHEET_NAMES</span>
        </div>
    </div>
</div>

<div class="flow-line color-clean"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 3: IMPUTATION ═══════════════════════ -->
<div class="layer layer-impute">🔧 Layer 3 — Imputation & Validation</div>
<div class="file-row">
    <div class="file-node node-impute">
        <div class="file-icon">🩹</div>
        <div class="file-name">data_imputer.py</div>
        <div class="file-desc">
            Fills missing values using<br>
            statistical methods (median, mode),<br>
            validates data integrity
        </div>
        <div class="file-output">
            <span class="output-tag">FINAL_Sales_QTY.csv</span>
            <span class="output-tag">FINAL_MFG_Date.csv</span>
            <span class="output-tag">FINAL_Documented_Loop_Times.csv</span>
            <span class="output-tag">FINAL_Receipt_to_Receipt_Data.csv</span>
        </div>
    </div>
    <div class="file-node node-impute">
        <div class="file-icon">🏭</div>
        <div class="file-name">mfg_generator.py</div>
        <div class="file-desc">
            Auto-creates MFG records for<br>
            containers in Sales but missing<br>
            from manufacturing tracking
        </div>
        <div class="file-output">
            <span class="output-tag">Serial Numbers</span>
            <span class="output-tag">MFG Dates</span>
            <span class="output-tag">Part Numbers</span>
        </div>
    </div>
    <div class="file-node node-impute">
        <div class="file-icon">📈</div>
        <div class="file-name">ewma_sync.py</div>
        <div class="file-desc">
            EWMA smoothing engine —<br>
            syncs demand signals across<br>
            time series data
        </div>
        <div class="file-output">
            <span class="output-tag">Smoothed Demand</span>
            <span class="output-tag">Trend Signals</span>
        </div>
    </div>
</div>

<div class="flow-line color-impute"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 4: ENGINES ═══════════════════════ -->
<div class="layer layer-engine">⚡ Layer 4 — Simulation & Intelligence Engines</div>
<div class="file-row">
    <div class="file-node node-engine">
        <div class="file-icon">🎲</div>
        <div class="file-name">fleet_sim.py</div>
        <div class="file-desc">
            Monte Carlo fleet simulation —<br>
            binary search for optimal fleet size<br>
            at target service level
        </div>
        <div class="file-output">
            <span class="output-tag">Optimal Fleet Size</span>
            <span class="output-tag">Simulation Charts</span>
        </div>
    </div>
    <div class="file-node node-engine">
        <div class="file-icon">🌐</div>
        <div class="file-name">live_twin_engine.py</div>
        <div class="file-desc">
            Digital twin — generates virtual<br>
            daily data based on historical<br>
            buying patterns & order qty
        </div>
        <div class="file-output">
            <span class="output-tag">Daily Orders</span>
            <span class="output-tag">Demand Forecast</span>
        </div>
    </div>
    <div class="file-node node-engine">
        <div class="file-icon">🔁</div>
        <div class="file-name">return_tracker.py</div>
        <div class="file-desc">
            Asset loop tracking &<br>
            EU compliance allocation —<br>
            Green → Intl, Amber → Domestic
        </div>
        <div class="file-output">
            <span class="output-tag">Loop Status</span>
            <span class="output-tag">Compliance Split</span>
        </div>
    </div>
</div>

<div class="flow-line color-engine"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 5: JSON ARTIFACTS ═══════════════════════ -->
<div class="layer layer-artifact">📦 Layer 5 — JSON Artifact Generation</div>
<div class="file-row">
    <div class="file-node node-artifact">
        <div class="file-icon">👥</div>
        <div class="file-name">customer_insights.json</div>
        <div class="file-desc">
            Per-customer order history,<br>
            dwell times, anomalies,<br>
            contracted loop-time data
        </div>
    </div>
    <div class="file-node node-artifact">
        <div class="file-icon">📋</div>
        <div class="file-name">item_metrics.json</div>
        <div class="file-desc">
            Per-product demand, dwell,<br>
            fleet size, asset ages —<br>
            simulation defaults
        </div>
    </div>
    <div class="file-node node-artifact">
        <div class="file-icon">⚠️</div>
        <div class="file-name">anomaly_archive.json</div>
        <div class="file-desc">
            Analyst-classified anomalies —<br>
            persistent record of resolved<br>
            demand outliers
        </div>
    </div>
</div>

<div class="flow-line color-artifact"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 5.5: AI CONTEXT ═══════════════════════ -->
<div class="file-row">
    <div class="file-node node-engine" style="max-width: 340px;">
        <div class="file-icon">🧠</div>
        <div class="file-name">ai_context.py</div>
        <div class="file-desc">
            Builds full database context payload for Möbius AI —<br>
            merges all 3 JSON artifacts + raw Excel slices<br>
            into a token-managed prompt for Gemini
        </div>
        <div class="file-output">
            <span class="output-tag">Customer Profiles</span>
            <span class="output-tag">Order History</span>
            <span class="output-tag">Anomaly Feed</span>
        </div>
    </div>
    <div class="file-node node-artifact" style="max-width: 340px;">
        <div class="file-icon">🗂️</div>
        <div class="file-name">anomaly_manager.py</div>
        <div class="file-desc">
            Loads & saves the Anomaly Archive —<br>
            persistent JSON record of classified<br>
            and resolved demand anomalies
        </div>
        <div class="file-output">
            <span class="output-tag">Archive I/O</span>
            <span class="output-tag">Classification Reasons</span>
        </div>
    </div>
</div>

<div class="flow-line color-artifact"><div class="dot-track"></div></div>

<!-- ═══════════════════════ LAYER 6: DASHBOARD ═══════════════════════ -->
<div class="layer layer-dash">🖥️ Layer 6 — Dashboard Modules</div>
<div class="file-row">
    <div class="file-node node-dash">
        <div class="file-icon">🏢</div>
        <div class="file-name">control_tower.py</div>
        <div class="file-desc">
            Executive KPIs, fleet health,<br>
            risk alerts, multi-agent<br>
            AI war room
        </div>
    </div>
    <div class="file-node node-dash">
        <div class="file-icon">📦</div>
        <div class="file-name">tracking.py</div>
        <div class="file-desc">
            Return status tracking,<br>
            serial inspector,<br>
            fleet registry
        </div>
    </div>
    <div class="file-node node-dash">
        <div class="file-icon">💰</div>
        <div class="file-name">real_world_sim.py</div>
        <div class="file-desc">
            What-if simulator,<br>
            EWMA forecasting,<br>
            Sankey asset flow
        </div>
    </div>
    <div class="file-node node-dash">
        <div class="file-icon">🌍</div>
        <div class="file-name">fleet_optimization.py</div>
        <div class="file-desc">
            Monte Carlo optimizer,<br>
            service-level charts,<br>
            fleet sizing engine
        </div>
    </div>
</div>

<div class="flow-line color-artifact"><div class="dot-track"></div></div>

<!-- ═══════════════════════ FINAL: APP SHELL ═══════════════════════ -->
<div class="file-row">
    <div class="file-node node-dash wide" style="border-color: rgba(6,182,212,0.4);">
        <div class="file-icon">🚀</div>
        <div class="file-name">app.py</div>
        <div class="file-desc">
            Global shell — page config, sidebar nav, background video,<br>
            glassmorphism CSS, data pipeline trigger, footer<br>
            <span style="color:rgba(6,182,212,0.7);">Orchestrates all modules into a unified Streamlit dashboard</span>
        </div>
    </div>
</div>

</div><!-- /pipeline -->
<script>
document.addEventListener('mousemove', e => {
    const iframe = window.frameElement;
    if (iframe) {
        const rect = iframe.getBoundingClientRect();
        window.parent.document.dispatchEvent(new MouseEvent('mousemove', {
            clientX: rect.left + e.clientX, clientY: rect.top + e.clientY
        }));
    }
});
</script>
</body>
</html>
'''


def _build_cicd_html() -> str:
    """Build a Technology Stack & Intelligence Layers showcase."""
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: transparent;
    color: white;
    padding: 20px 20px 40px;
}
.showcase { max-width: 1100px; margin: 0 auto; }

/* ── Section header ── */
.section-hdr {
    display: flex; align-items: center; gap: 14px;
    width: 100%;
    background: linear-gradient(135deg, rgba(20,22,30,0.9) 0%, rgba(30,34,44,0.85) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 4px solid;
    border-radius: 14px;
    padding: 16px 28px;
    font-size: 0.95rem; font-weight: 800; letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 18px; margin-top: 28px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    transition: all 0.3s ease;
}
.section-hdr:hover {
    border-left-width: 6px;
    transform: translateX(2px);
}
.section-hdr:first-child { margin-top: 0; }

/* ── Tech stack grid ── */
.tech-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
    gap: 12px; margin-bottom: 8px;
}
.tech-card {
    background: rgba(30,32,40,0.75);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 14px; text-align: center;
    transition: all 0.35s ease;
    position: relative; overflow: hidden;
}
.tech-card::before {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0;
    height: 3px; border-radius: 0 0 14px 14px;
    transition: height 0.3s ease;
}
.tech-card:hover {
    transform: translateY(-5px);
    border-color: rgba(255,255,255,0.2);
    box-shadow: 0 10px 35px rgba(0,0,0,0.5);
}
.tech-card:hover::before { height: 5px; }
.tc-icon { font-size: 2rem; margin-bottom: 8px; }
.tc-name { font-size: 0.82rem; font-weight: 700; margin-bottom: 3px; }
.tc-role { font-size: 0.62rem; color: rgba(255,255,255,0.4); line-height: 1.4; }
.tc-ver {
    display: inline-block; margin-top: 6px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px; padding: 1px 8px;
    font-size: 0.55rem; font-family: "SF Mono", monospace;
    color: rgba(255,255,255,0.35);
}

.tc-python::before { background: linear-gradient(90deg, #3776AB, #FFD43B); }
.tc-python .tc-name { color: #FFD43B; }
.tc-streamlit::before { background: linear-gradient(90deg, #FF4B4B, #FF8C8C); }
.tc-streamlit .tc-name { color: #FF4B4B; }
.tc-pandas::before { background: linear-gradient(90deg, #150458, #E70488); }
.tc-pandas .tc-name { color: #E70488; }
.tc-plotly::before { background: linear-gradient(90deg, #3F4F75, #636EFA); }
.tc-plotly .tc-name { color: #636EFA; }
.tc-gemini::before { background: linear-gradient(90deg, #4285F4, #34A853); }
.tc-gemini .tc-name { color: #8AB4F8; }
.tc-numpy::before { background: linear-gradient(90deg, #4DABCF, #4B73B8); }
.tc-numpy .tc-name { color: #4DABCF; }

/* ── Intelligence layers ── */
.intel-layer {
    display: flex; align-items: center; gap: 20px;
    padding: 20px 28px;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    margin-bottom: 12px;
    transition: all 0.35s ease;
    position: relative; overflow: hidden;
}
.intel-layer::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0;
    width: 4px; border-radius: 16px 0 0 16px;
    transition: width 0.3s ease;
}
.intel-layer:hover {
    transform: translateX(4px);
    border-color: rgba(255,255,255,0.12);
    box-shadow: 0 6px 28px rgba(0,0,0,0.4);
}
.intel-layer:hover::before { width: 6px; }
.il-num {
    font-size: 2.2rem; font-weight: 900;
    opacity: 0.15; min-width: 50px; text-align: center;
    font-family: "SF Mono", monospace;
}
.il-icon { font-size: 2rem; min-width: 40px; text-align: center; }
.il-content { flex: 1; }
.il-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 4px; }
.il-desc { font-size: 0.7rem; color: rgba(255,255,255,0.45); line-height: 1.55; }
.il-tags { margin-top: 8px; }
.il-tag {
    display: inline-block;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px; padding: 2px 10px;
    font-size: 0.6rem; font-family: "SF Mono", monospace;
    color: rgba(255,255,255,0.4); margin: 2px;
}

.il-data { background: rgba(212,135,28,0.04); }
.il-data::before { background: #D4871C; }
.il-data .il-title { color: #E8993E; }
.il-data .il-num { color: #D4871C; }

.il-analytics { background: rgba(34,197,94,0.04); }
.il-analytics::before { background: #22C55E; }
.il-analytics .il-title { color: #4ADE80; }
.il-analytics .il-num { color: #22C55E; }

.il-simulation { background: rgba(168,85,247,0.04); }
.il-simulation::before { background: #A855F7; }
.il-simulation .il-title { color: #C084FC; }
.il-simulation .il-num { color: #A855F7; }

.il-ai { background: rgba(59,130,246,0.04); }
.il-ai::before { background: #3B82F6; }
.il-ai .il-title { color: #60A5FA; }
.il-ai .il-num { color: #3B82F6; }

/* ── Flow connector ── */
.flow-connector {
    text-align: center; margin: -4px 0; z-index: 1; position: relative;
}
.flow-connector .fc-dot {
    width: 2px; height: 20px; margin: 0 auto;
    background: rgba(255,255,255,0.06);
    position: relative; overflow: hidden;
}
.flow-connector .fc-dot::after {
    content: '';
    position: absolute; top: -6px; left: -1px;
    width: 4px; height: 6px; border-radius: 3px;
    background: currentColor;
    animation: fc-flow 1.2s linear infinite;
}
@keyframes fc-flow {
    0% { top: -6px; opacity: 0; }
    30% { opacity: 1; }
    70% { opacity: 1; }
    100% { top: 20px; opacity: 0; }
}
.fc-orange .fc-dot { color: #D4871C; }
.fc-green .fc-dot { color: #22C55E; }
.fc-purple .fc-dot { color: #A855F7; }

/* ── Stats banner ── */
.stats-banner {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-top: 8px;
}
.stat-card {
    background: rgba(30,32,40,0.75);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 18px 14px;
    text-align: center; transition: all 0.3s ease;
}
.stat-card:hover {
    transform: translateY(-3px);
    border-color: rgba(212,135,28,0.3);
    box-shadow: 0 6px 24px rgba(0,0,0,0.4);
}
.stat-value {
    font-size: 1.6rem; font-weight: 900;
    background: linear-gradient(135deg, #D4871C, #E8993E);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.stat-label {
    font-size: 0.62rem; color: rgba(255,255,255,0.35);
    margin-top: 4px; text-transform: uppercase;
    letter-spacing: 0.5px;
}
</style>
</head>
<body>
<div class="showcase">

<!-- ═══════ TECH STACK ═══════ -->
<div class="section-hdr" style="border-left-color:#D4871C;color:#D4871C;">
    🛠️ Technology Stack
</div>
<div class="tech-grid">
    <div class="tech-card tc-python">
        <div class="tc-icon"><svg viewBox="0 0 256 255" xmlns="http://www.w3.org/2000/svg" width="40" height="40"><defs><linearGradient id="pyA" x1="12.96%" y1="12.07%" x2="79.64%" y2="78.8%"><stop offset="0%" stop-color="#387EB8"/><stop offset="100%" stop-color="#366994"/></linearGradient><linearGradient id="pyB" x1="19.13%" y1="20.58%" x2="90.43%" y2="88.01%"><stop offset="0%" stop-color="#FFC836"/><stop offset="100%" stop-color="#FFD43B"/></linearGradient></defs><path d="M126.916.072c-64.832 0-60.784 28.115-60.784 28.115l.072 29.128h61.868v8.745H41.631S.145 61.355.145 126.77c0 65.417 36.21 63.097 36.21 63.097h21.61v-30.356s-1.165-36.21 35.632-36.21h61.362s34.475.557 34.475-33.319V33.97S194.67.072 126.916.072zM92.802 19.66a11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13 11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.13z" fill="url(#pyA)"/><path d="M128.757 254.126c64.832 0 60.784-28.115 60.784-28.115l-.072-29.127H127.6v-8.746h86.441s41.486 4.705 41.486-60.712c0-65.416-36.21-63.096-36.21-63.096h-21.61v30.355s1.165 36.21-35.632 36.21h-61.362s-34.475-.557-34.475 33.32v56.013s-5.235 33.897 62.518 33.897zm34.114-19.586a11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.131 11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13z" fill="url(#pyB)"/></svg></div>
        <div class="tc-name">Python</div>
        <div class="tc-role">Core language<br>All backend logic</div>
        <div class="tc-ver">3.11+</div>
    </div>
    <div class="tech-card tc-streamlit">
        <div class="tc-icon"><svg viewBox="0 0 235 235" xmlns="http://www.w3.org/2000/svg" width="40" height="40"><path d="M117.5 0L235 200H0z" fill="#FF4B4B" opacity="0.7"/><path d="M117.5 45L205 200H30z" fill="#FF4B4B"/><path d="M117.5 95L175 200H60z" fill="#fff" opacity="0.4"/></svg></div>
        <div class="tc-name">Streamlit</div>
        <div class="tc-role">Web framework<br>Reactive UI engine</div>
        <div class="tc-ver">1.50.0</div>
    </div>
    <div class="tech-card tc-pandas">
        <div class="tc-icon"><svg viewBox="0 0 210 280" xmlns="http://www.w3.org/2000/svg" width="34" height="40"><g fill="#150458"><rect x="20" y="0" width="45" height="80" rx="4"/><rect x="20" y="100" width="45" height="80" rx="4"/><rect x="20" y="200" width="45" height="80" rx="4"/><rect x="145" y="0" width="45" height="80" rx="4"/><rect x="145" y="100" width="45" height="80" rx="4"/><rect x="145" y="200" width="45" height="80" rx="4"/></g><g fill="#E70488"><rect x="82" y="40" width="45" height="80" rx="4"/><rect x="82" y="160" width="45" height="80" rx="4"/></g></svg></div>
        <div class="tc-name">Pandas</div>
        <div class="tc-role">Data wrangling<br>ETL backbone</div>
        <div class="tc-ver">2.x</div>
    </div>
    <div class="tech-card tc-plotly">
        <div class="tc-icon"><svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect x="20" y="80" width="30" height="100" rx="4" fill="#636EFA"/><rect x="60" y="40" width="30" height="140" rx="4" fill="#EF553B"/><rect x="100" y="100" width="30" height="80" rx="4" fill="#00CC96"/><rect x="140" y="20" width="30" height="160" rx="4" fill="#AB63FA"/></svg></div>
        <div class="tc-name">Plotly</div>
        <div class="tc-role">Interactive charts<br>Sankey, bar, scatter</div>
        <div class="tc-ver">5.x</div>
    </div>
    <div class="tech-card tc-gemini">
        <div class="tc-icon"><svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="40" height="40"><defs><linearGradient id="gemG" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#4285F4"/><stop offset="25%" stop-color="#9B72CB"/><stop offset="50%" stop-color="#D96570"/><stop offset="75%" stop-color="#D96570"/><stop offset="100%" stop-color="#9B72CB"/></linearGradient></defs><path d="M100 0C100 55 55 100 0 100C55 100 100 145 100 200C100 145 145 100 200 100C145 100 100 55 100 0Z" fill="url(#gemG)"/></svg></div>
        <div class="tc-name">Google Gemini</div>
        <div class="tc-role">AI chat engine<br>Multi-agent reasoning</div>
        <div class="tc-ver">2.0 Flash</div>
    </div>
    <div class="tech-card tc-numpy">
        <div class="tc-icon"><svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" width="40" height="40"><polygon points="100,10 180,55 180,145 100,190 20,145 20,55" fill="none" stroke="#4DABCF" stroke-width="8"/><text x="100" y="120" text-anchor="middle" font-family="Arial" font-weight="900" font-size="72" fill="#4B73B8">N</text></svg></div>
        <div class="tc-name">NumPy</div>
        <div class="tc-role">Monte Carlo sim<br>Statistical engine</div>
        <div class="tc-ver">1.26+</div>
    </div>
</div>

<!-- ═══════ INTELLIGENCE LAYERS ═══════ -->
<div class="section-hdr" style="border-left-color:#A855F7;color:#A855F7;">
    🧠 Intelligence Layers
</div>

<div class="intel-layer il-data">
    <div class="il-num">01</div>
    <div class="il-icon">📁</div>
    <div class="il-content">
        <div class="il-title">Data Foundation</div>
        <div class="il-desc">
            Raw Excel ingestion → sheet-level cleaning → statistical imputation → validated FINAL datasets.
            Every data point is traceable from source to dashboard.
        </div>
        <div class="il-tags">
            <span class="il-tag">data_cleaner.py</span>
            <span class="il-tag">data_imputer.py</span>
            <span class="il-tag">mfg_generator.py</span>
            <span class="il-tag">config.py</span>
        </div>
    </div>
</div>

<div class="flow-connector fc-orange"><div class="fc-dot"></div></div>

<div class="intel-layer il-analytics">
    <div class="il-num">02</div>
    <div class="il-icon">📈</div>
    <div class="il-content">
        <div class="il-title">Analytics Engine</div>
        <div class="il-desc">
            EWMA demand smoothing, anomaly detection with Z-score classification,
            customer behavioral profiling, and per-product metric aggregation into JSON artifacts.
        </div>
        <div class="il-tags">
            <span class="il-tag">ewma_sync.py</span>
            <span class="il-tag">anomaly_manager.py</span>
            <span class="il-tag">customer_insights.json</span>
            <span class="il-tag">item_metrics.json</span>
        </div>
    </div>
</div>

<div class="flow-connector fc-green"><div class="fc-dot"></div></div>

<div class="intel-layer il-simulation">
    <div class="il-num">03</div>
    <div class="il-icon">🎲</div>
    <div class="il-content">
        <div class="il-title">Simulation Core</div>
        <div class="il-desc">
            Monte Carlo fleet optimization with binary search for optimal fleet sizing,
            digital twin engine for daily demand simulation, and EU compliance-aware asset allocation
            (Green → International, Amber → Domestic).
        </div>
        <div class="il-tags">
            <span class="il-tag">fleet_sim.py</span>
            <span class="il-tag">live_twin_engine.py</span>
            <span class="il-tag">return_tracker.py</span>
        </div>
    </div>
</div>

<div class="flow-connector fc-purple"><div class="fc-dot"></div></div>

<div class="intel-layer il-ai">
    <div class="il-num">04</div>
    <div class="il-icon">🧠</div>
    <div class="il-content">
        <div class="il-title">AI Intelligence</div>
        <div class="il-desc">
            Gemini-powered chat with full database context injection. Multi-agent war room
            with 4 specialist agents (Data Validator, Inventory, Logistics, Senior Manager)
            for collaborative decision-making. Image and file attachment support.
        </div>
        <div class="il-tags">
            <span class="il-tag">ai_context.py</span>
            <span class="il-tag">mobius_ai.py</span>
            <span class="il-tag">control_tower.py</span>
        </div>
    </div>
</div>

<!-- ═══════ KEY CAPABILITIES ═══════ -->
<div class="section-hdr" style="border-left-color:#06B6D4;color:#06B6D4;">
    ⚡ Key Capabilities
</div>
<div class="stats-banner">
    <div class="stat-card">
        <div class="stat-value">15+</div>
        <div class="stat-label">Python Modules</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">5</div>
        <div class="stat-label">Dashboard Pages</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">4</div>
        <div class="stat-label">AI Agents</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">365</div>
        <div class="stat-label">Days Simulated</div>
    </div>
</div>

</div><!-- /showcase -->
<script>
document.addEventListener('mousemove', e => {
    const iframe = window.frameElement;
    if (iframe) {
        const rect = iframe.getBoundingClientRect();
        window.parent.document.dispatchEvent(new MouseEvent('mousemove', {
            clientX: rect.left + e.clientX, clientY: rect.top + e.clientY
        }));
    }
});
</script>
</body>
</html>
'''


def _build_problems_html() -> str:
    """Build a Problem Statement page showing business challenges and solutions."""
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: transparent;
    color: white;
    padding: 20px 20px 40px;
}
.problems { max-width: 1100px; margin: 0 auto; }

/* ── Section header ── */
.section-hdr {
    display: flex; align-items: center; gap: 14px;
    width: 100%;
    background: linear-gradient(135deg, rgba(20,22,30,0.9) 0%, rgba(30,34,44,0.85) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 4px solid;
    border-radius: 14px;
    padding: 16px 28px;
    font-size: 0.95rem; font-weight: 800; letter-spacing: 2.5px;
    text-transform: uppercase;
    margin-bottom: 20px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

/* ── Problem card ── */
.problem-card {
    display: flex; gap: 24px; align-items: flex-start;
    background: rgba(30,32,40,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 14px;
    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative; overflow: hidden;
    /* Start hidden for scroll reveal */
    opacity: 0;
    transform: translateX(-20px);
}
.problem-card.revealed {
    opacity: 1;
    transform: translateX(0);
}
.problem-card::before {
    content: "";
    position: absolute; left: 0; top: 0; bottom: 0;
    width: 4px; border-radius: 16px 0 0 16px;
}
.problem-card:hover {
    transform: translateX(4px) scale(1.01);
    border-color: rgba(255,255,255,0.12);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.problem-card:hover::before { width: 6px; }

/* Card colors */
.pc-red::before { background: #EF4444; }
.pc-orange::before { background: #F59E0B; }
.pc-yellow::before { background: #EAB308; }
.pc-purple::before { background: #A855F7; }
.pc-blue::before { background: #3B82F6; }
.pc-cyan::before { background: #06B6D4; }

.pc-num {
    font-size: 2.4rem; font-weight: 900;
    font-family: "SF Mono", monospace;
    min-width: 48px; text-align: center;
    opacity: 0.12;
}
.pc-red .pc-num { color: #EF4444; }
.pc-orange .pc-num { color: #F59E0B; }
.pc-yellow .pc-num { color: #EAB308; }
.pc-purple .pc-num { color: #A855F7; }
.pc-blue .pc-num { color: #3B82F6; }
.pc-cyan .pc-num { color: #06B6D4; }

.pc-icon { font-size: 2rem; min-width: 36px; text-align: center; }
.pc-body { flex: 1; }
.pc-title { font-size: 1rem; font-weight: 700; margin-bottom: 6px; }
.pc-red .pc-title { color: #F87171; }
.pc-orange .pc-title { color: #FBBF24; }
.pc-yellow .pc-title { color: #FDE047; }
.pc-purple .pc-title { color: #C084FC; }
.pc-blue .pc-title { color: #60A5FA; }
.pc-cyan .pc-title { color: #22D3EE; }

.pc-desc {
    font-size: 0.75rem; color: rgba(255,255,255,0.45);
    line-height: 1.6; margin-bottom: 10px;
}

/* Solution badge */
.pc-solution {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(212,135,28,0.08);
    border: 1px solid rgba(212,135,28,0.2);
    border-radius: 10px; padding: 8px 14px;
}
.pc-solution .sol-label {
    font-size: 0.6rem; font-weight: 700;
    color: #D4871C; text-transform: uppercase;
    letter-spacing: 1px;
}
.pc-solution .sol-text {
    font-size: 0.7rem; color: rgba(255,255,255,0.6);
}

/* ── Impact summary ── */
.impact-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px; margin-top: 8px;
}
.impact-card {
    background: rgba(30,32,40,0.75);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 20px 16px;
    text-align: center; transition: all 0.3s ease;
}
.impact-card:hover {
    transform: translateY(-3px);
    border-color: rgba(239,68,68,0.3);
    box-shadow: 0 6px 24px rgba(0,0,0,0.4);
}
.impact-value {
    font-size: 1.5rem; font-weight: 900;
    background: linear-gradient(135deg, #EF4444, #F59E0B);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.impact-label {
    font-size: 0.62rem; color: rgba(255,255,255,0.35);
    margin-top: 4px; text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* -- Context blocks -- */
.context-block {
    background: rgba(25,28,36,0.7);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 24px 30px;
    margin-bottom: 16px;
    transition: all 0.4s ease;
}
.context-block:hover {
    border-color: rgba(255,255,255,0.1);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.ctx-title {
    font-size: 0.85rem; font-weight: 700;
    margin-bottom: 10px; display: flex;
    align-items: center; gap: 10px;
}
.ctx-body {
    font-size: 0.76rem; color: rgba(255,255,255,0.5);
    line-height: 1.75;
}
.ctx-body strong { color: rgba(255,255,255,0.75); font-weight: 600; }
.key-questions {
    margin-top: 12px; padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.05);
}
.kq-item {
    display: flex; align-items: flex-start; gap: 10px;
    margin-bottom: 8px;
}
.kq-bullet {
    min-width: 20px; height: 20px;
    background: rgba(212,135,28,0.15);
    border: 1px solid rgba(212,135,28,0.3);
    border-radius: 6px; text-align: center;
    font-size: 0.55rem; line-height: 20px;
    color: #D4871C; font-weight: 700;
}
.kq-text {
    font-size: 0.72rem; color: rgba(255,255,255,0.45);
    line-height: 1.5;
}
.stat-highlight {
    display: inline-block;
    background: rgba(212,135,28,0.1);
    border: 1px solid rgba(212,135,28,0.2);
    border-radius: 6px; padding: 1px 8px;
    color: #E8993E; font-weight: 700;
    font-size: 0.72rem;
}
</style>
</head>
<body>
<div class="problems">

<!-- PROJECT OVERVIEW -->
<div class="section-hdr" style="border-left-color:#D4871C;color:#D4871C;">
    🎯 Project Overview
</div>
<div class="context-block">
    <div class="ctx-title" style="color:#E8993E;">📋 Objective</div>
    <div class="ctx-body">
        This project aims to analyze and optimize the management of <strong>returnable assets</strong> such as totes,
        drums, and accessories within the supply chain. The objective is to research industry's best
        practices for calculating <strong>optimal fleet sizes</strong> that balance cost efficiency, asset availability,
        and operational flexibility. The project will evaluate current asset utilization, return cycle
        times, and loss rates to identify gaps and improvement opportunities. In addition, <strong>data-driven
        tracking and monitoring methods</strong> will be developed to provide real-time visibility of assets
        throughout the loop, incorporating risk factors such as time delays, cost implications, and
        availability constraints. The outcome will be a <strong>standardized approach for rightsizing</strong> the
        returnable asset fleet and an enhanced tracking process that reduces waste, minimizes
        shortages, and supports continuous improvement in supply chain performance.
    </div>

    <div style="border-top:1px solid rgba(255,255,255,0.06); margin:18px 0;"></div>

    <div class="ctx-title" style="color:#C084FC;">🏢 Background</div>
    <div class="ctx-body">
        MLI currently has approximately <span class="stat-highlight">$20 million</span> invested in returnable asset fleets across its
        customer base. There are multiple different fleet operations, from direct restocks to 3PL
        consignment warehouses. Several factors impact the ability to effectively track and manage
        these assets, including <strong>limited information sharing from customers</strong>, regulatory restrictions such
        as the <strong>EU requirement that packaging older than 4.25 years cannot be shipped</strong>, and gaps in
        cross-departmental collaboration within MLI. At present, fleet size calculations are managed
        through <strong>Excel-based data packages</strong>, which provide limited functionality — tracking
        physical movement of assets remains constrained. As a result, MLI often experiences <strong>runout
        situations</strong> where insufficient packaging is available to meet upcoming orders, driven by a
        lack of visibility into return schedules. While technologies such as RFID tagging and GPS
        tracking have been explored, the <strong>high cost</strong> associated with deploying these solutions across
        the large fleet has so far prevented implementation.
    </div>
</div>


</div><!-- /problems -->

<script>
const obs = new IntersectionObserver((entries) => {
    entries.forEach((e, i) => {
        if (e.isIntersecting) {
            setTimeout(() => e.target.classList.add('revealed'), i * 120);
        }
    });
}, { threshold: 0.15 });
document.querySelectorAll('.problem-card').forEach(el => obs.observe(el));

// Forward mouse events to parent for background dot animation
document.addEventListener('mousemove', e => {
    const iframe = window.frameElement;
    if (iframe) {
        const rect = iframe.getBoundingClientRect();
        window.parent.document.dispatchEvent(new MouseEvent('mousemove', {
            clientX: rect.left + e.clientX, clientY: rect.top + e.clientY
        }));
    }
});
</script>
<script>
// Fallback: reveal all cards after short delay if IntersectionObserver doesn't fire
setTimeout(function() {
    document.querySelectorAll('.problem-card:not(.revealed)').forEach(function(el, i) {
        setTimeout(function() { el.classList.add('revealed'); }, i * 120);
    });
}, 500);
</script>
</body>
</html>
'''
