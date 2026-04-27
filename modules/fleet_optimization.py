"""
modules/fleet_optimization.py
-----------------------------
Fleet Optimization Dashboard — Monte Carlo simulation & customer deep-dive.

Renders:
  - Global fleet health banner
  - Inline product selector, customer insights, simulation parameters
  - Simulation results (run_simulation), anomaly detection, customer deep-dive
  - Footer
"""
from __future__ import annotations

import os
import json
import base64
import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fleet_sim import run_simulation, get_item_names, get_item_defaults
from anomaly_manager import (
    load_archive, archive_anomalies, build_archive_entry,
    get_archived_ids, ANOMALY_REASONS
)


# Constants
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSIGHTS_PATH  = os.path.join(_BASE, "customer_insights.json")
GIF_PATH       = os.path.join(_BASE, "Mobious.gif")
DATA_FILE_PATH = os.path.join(_BASE, "MLI Capstone Data.xlsx")

FREQ_BADGE = {
    "Consistent": "🟢",
    "Regular":    "🔵",
    "Seasonal":   "🟡",
    "Sporadic":   "🔴",
}

# TOOLTIP_CSS already injected globally in app.py — no need to duplicate here


# ── Shared helper functions (moved from app.py) ──────────────────────────────

@st.cache_data
def load_customer_insights(data_mtime: float) -> dict:
    """Load customer_insights.json; cache-busted by data_mtime."""
    if os.path.exists(INSIGHTS_PATH):
        try:
            with open(INSIGHTS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def generate_dwell_insight(actual_dwell, contracted_dwell) -> tuple:
    """Compare actual vs contracted dwell time → (status, message)."""
    try:
        actual     = float(actual_dwell)
        contracted = float(contracted_dwell)
    except (ValueError, TypeError):
        return ("error", "ℹ️ Data Gap: No contracted loop time found. Action: Audit customer contract.")
    if actual > contracted * 1.2:
        return (
            "warning",
            "⚠️ **Risk Detected:** Customer is retaining assets significantly longer than contracted. "
            "**Recommended Action:** Dispatch a 3PL truck to retrieve empties and enforce contract terms.",
        )
    elif actual < contracted * 0.9:
        return (
            "success",
            "✅ **High Efficiency:** Customer loops assets faster than planned. "
            "**Recommended Action:** Consider this customer for priority fulfillment during asset shortages.",
        )
    else:
        return (
            "info",
            "📊 **Optimal Operation:** Customer is returning assets within expected contract parameters. "
            "**Action:** Continue standard monitoring.",
        )


def make_sparkline(data: list, color: str, height: int = 35, margin: int = 4) -> go.Figure:
    """Build a compact, axis-free Plotly sparkline."""
    fig = go.Figure(go.Scatter(
        y=data, mode="lines",
        line=dict(color=color, width=2.5, shape="spline"),
    ))
    fig.update_layout(
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=margin, r=margin, t=margin, b=margin),
        height=height, hovermode=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


@st.cache_data
def cached_get_item_names(data_mtime: float) -> list:
    return get_item_names()


@st.cache_data
def cached_get_item_defaults(item_name: str, data_mtime: float) -> tuple:
    return get_item_defaults(item_name)


def render():
    """Render the Fleet Optimization Dashboard page."""

    # Data mtime for cache invalidation
    try:
        data_mtime = os.path.getmtime(DATA_FILE_PATH)
    except FileNotFoundError:
        data_mtime = 0



    # ── Verify items are available before proceeding ──────────────────────────────

    item_names = cached_get_item_names(data_mtime)
    if not item_names:
        st.error("No item metrics found. Please check data files.")
        st.stop()


    # ── 8. Global fleet health banner ─────────────────────────────────────────────
    # Aggregates all customer insights to show a high-level portfolio health snapshot.

    all_insights    = load_customer_insights(data_mtime)
    total_customers = sum(len(v) for v in all_insights.values())
    total_anomalies = sum(len(c.get('anomalies', [])) for v in all_insights.values() for c in v)
    global_demand   = sum(c.get('annual_qty', 0) for v in all_insights.values() for c in v)

    st.markdown(f"""
        <div style="
            background: rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(40px) saturate(180%);
            -webkit-backdrop-filter: blur(40px) saturate(180%);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-top: 1px solid rgba(255, 255, 255, 0.5);
            border-left: 1px solid rgba(255, 255, 255, 0.4);
            padding: 15px 30px;
            border-radius: 24px;
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.12), inset 0 0 0 1px rgba(255,255,255,0.1);
            margin-bottom: 25px;
        ">
            <div style="font-size:1.1rem;font-weight:bold;">🌍 Global Fleet Health Overview</div>
            <div style="display:flex;gap:40px;">
                <div style="text-align:center;">
                    <div style="font-size:0.8rem;opacity:0.8;">Total Active Customers</div>
                    <div style="font-size:1.4rem;font-weight:800;">{total_customers:,}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:0.8rem;opacity:0.8;">Global Anomalies Detected</div>
                    <div style="font-size:1.4rem;font-weight:800;">{total_anomalies:,}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:0.8rem;opacity:0.8;">Aggregate Annual Demand</div>
                    <div style="font-size:1.4rem;font-weight:800;">{int(global_demand):,} Units</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


    # ── Product selector + data load (needed by both columns below) ───────────
    selected_item = st.selectbox("📦 Select Product", item_names, key="fo_product")

    item_demand, item_dwell, item_fleet_size, _ = cached_get_item_defaults(selected_item, data_mtime)
    item_insights = all_insights.get(selected_item, [])

    # ── Inline control panel — replaces the old sidebar ───────────────────────
    _ctrl_left, _ctrl_right = st.columns([3, 2], gap="large")

    # ── LEFT COLUMN: Product-Specific Strategic Tiers ────────────────────────
    with _ctrl_left:
        # ── Tiering Engine ────────────────────────────────────────────────────
        # Score each customer for THIS product on 4 weighted dimensions:
        #   Volume Rank (35%) · Consistency (25%) · Anomaly Density (20%) · Contract Adherence (20%)

        def _compute_tiers(customers: list) -> list:
            """Score and assign a tier to each customer for the current product."""
            if not customers:
                return []

            max_annual = max(c.get('annual_qty', 0) for c in customers) or 1

            scored = []
            for c in customers:
                annual   = c.get('annual_qty', 0)
                monthly  = c.get('avg_monthly_units', 0)
                active   = c.get('active_months', 0)
                total_mo = c.get('total_months', 1) or 1
                n_anom   = len(c.get('anomalies', []))
                freq     = c.get('frequency_label', 'N/A')
                dwell    = c.get('avg_dwell_time', None)
                doc_max  = c.get('doc_consignment_max', None)

                # 1) Volume score (0-100): percentile within this product
                vol_score = round(100 * annual / max_annual, 1)

                # 2) Consistency score (0-100): active months ratio
                consist_score = round(100 * active / total_mo)

                # 3) Anomaly density score (0-100): lower anomalies / order = better
                total_orders = len(c.get('orders', c.get('history', [])))
                if total_orders > 0:
                    anom_rate = n_anom / total_orders
                    anom_score = round(max(0, 100 - anom_rate * 500))  # 20% anomaly rate = 0
                else:
                    anom_score = 50  # neutral if no orders

                # 4) Contract adherence score (0-100): dwell vs documented max
                if isinstance(dwell, (int, float)) and isinstance(doc_max, (int, float)) and doc_max > 0:
                    dwell_ratio = dwell / doc_max
                    if dwell_ratio <= 1.0:
                        adhere_score = 100
                    elif dwell_ratio <= 1.5:
                        adhere_score = round(100 - (dwell_ratio - 1.0) * 200)
                    else:
                        adhere_score = max(0, round(100 - (dwell_ratio - 1.0) * 100))
                else:
                    adhere_score = 60  # neutral if no contract data

                # Weighted composite (0-100)
                composite = round(
                    vol_score * 0.35 +
                    consist_score * 0.25 +
                    anom_score * 0.20 +
                    adhere_score * 0.20,
                    1
                )

                # Assign tier
                if composite >= 75:
                    tier = "Strategic"
                elif composite >= 55:
                    tier = "Growth"
                elif composite >= 35:
                    tier = "Maintain"
                elif composite >= 18:
                    tier = "Monitor"
                else:
                    tier = "Deprioritize"

                scored.append({
                    **c,
                    'composite_score': composite,
                    'vol_score': vol_score,
                    'consist_score': consist_score,
                    'anom_score': anom_score,
                    'adhere_score': adhere_score,
                    'tier': tier,
                })

            scored.sort(key=lambda x: x['composite_score'], reverse=True)
            return scored

        tiered = _compute_tiers(item_insights)

        # ── Cross-product lookup for multi-product customers ──────────────────
        cross_product_map = {}
        for prod_name, prod_custs in all_insights.items():
            if prod_name == selected_item:
                continue
            prod_tiered = _compute_tiers(prod_custs)
            for ct in prod_tiered:
                cross_product_map.setdefault(ct['customer'], []).append({
                    'product': prod_name,
                    'tier':    ct['tier'],
                    'annual':  ct.get('annual_qty', 0),
                    'score':   ct['composite_score'],
                })

        # ── Tier config ───────────────────────────────────────────────────────
        TIER_CONFIG = {
            "Strategic":     {"color": "#22c55e", "icon": "🏆", "border": "#22c55e", "bg": "rgba(34,197,94,0.06)"},
            "Growth":        {"color": "#38bdf8", "icon": "📈", "border": "#38bdf8", "bg": "rgba(56,189,248,0.06)"},
            "Maintain":      {"color": "#a78bfa", "icon": "📊", "border": "#a78bfa", "bg": "rgba(167,139,250,0.06)"},
            "Monitor":       {"color": "#facc15", "icon": "👁️", "border": "#facc15", "bg": "rgba(250,204,21,0.06)"},
            "Deprioritize":  {"color": "#ef4444", "icon": "⚠️", "border": "#ef4444", "bg": "rgba(239,68,68,0.05)"},
        }

        # ── Header ────────────────────────────────────────────────────────────
        st.markdown(f'''
        <div style="font-size:1.15rem;font-weight:800;color:white;margin-bottom:2px;
                    display:flex;align-items:center;gap:8px;">
            🎯 <span>Strategic Tiering — {selected_item}</span>
        </div>
        <div style="font-size:0.78rem;color:rgba(255,255,255,0.4);margin-bottom:12px;">
            Product-specific tiers scored on <b style="color:#facc15;">volume</b> (35%),
            <b style="color:#22c55e;">consistency</b> (25%),
            <b style="color:#ef4444;">anomaly density</b> (20%),
            and <b style="color:#a78bfa;">contract adherence</b> (20%)
        </div>
        ''', unsafe_allow_html=True)

        if not tiered:
            st.caption("No customer data available for this product.")
        else:
            total_annual = sum(c.get('annual_qty', 0) for c in tiered)

            # ── Tier distribution bar ─────────────────────────────────────────
            tier_counts = {}
            for t in tiered:
                tier_counts[t['tier']] = tier_counts.get(t['tier'], 0) + 1

            bar_parts = ""
            for tier_name in ["Strategic", "Growth", "Maintain", "Monitor", "Deprioritize"]:
                cnt = tier_counts.get(tier_name, 0)
                if cnt == 0:
                    continue
                pct = round(100 * cnt / len(tiered))
                cfg = TIER_CONFIG[tier_name]
                bar_parts += (
                    f'<div style="flex:{pct};background:{cfg["color"]};height:100%;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:0.65rem;font-weight:700;color:#000;'
                    f'white-space:nowrap;overflow:hidden;min-width:20px;"'
                    f' title="{tier_name}: {cnt}">'
                    f'{cfg["icon"]} {cnt}'
                    f'</div>'
                )

            st.markdown(f'''
<div style="margin-bottom:10px;">
  <div style="display:flex;gap:2px;height:22px;border-radius:6px;overflow:hidden;">
    {bar_parts}
  </div>
</div>
            ''', unsafe_allow_html=True)

            # ── Tier filter tabs (clickable buttons) ──────────────────────────
            TIERS_ORDER = ["All", "Strategic", "Growth", "Maintain", "Monitor", "Deprioritize"]
            PER_PAGE = 5

            # Init session state for filter + page
            if "tier_filter" not in st.session_state:
                st.session_state.tier_filter = "All"
            if "tier_page" not in st.session_state:
                st.session_state.tier_page = 0

            # Build filter buttons
            filter_cols = st.columns(len(TIERS_ORDER))
            for i, tn in enumerate(TIERS_ORDER):
                with filter_cols[i]:
                    if tn == "All":
                        label = f"All ({len(tiered)})"
                        btn_type = "primary" if st.session_state.tier_filter == "All" else "secondary"
                    else:
                        cnt = tier_counts.get(tn, 0)
                        if cnt == 0:
                            st.button(f"{TIER_CONFIG[tn]['icon']} 0", disabled=True,
                                      use_container_width=True, key=f"tf_{tn}")
                            continue
                        label = f"{TIER_CONFIG[tn]['icon']} {cnt}"
                        btn_type = "primary" if st.session_state.tier_filter == tn else "secondary"

                    if st.button(label, type=btn_type, use_container_width=True, key=f"tf_{tn}"):
                        st.session_state.tier_filter = tn
                        st.session_state.tier_page = 0
                        st.rerun()

            # ── Filter customers ──────────────────────────────────────────────
            active_filter = st.session_state.tier_filter
            if active_filter == "All":
                filtered = tiered
            else:
                filtered = [c for c in tiered if c['tier'] == active_filter]

            if not filtered:
                st.caption("No customers in this tier.")
            else:
                # ── Tier group header ─────────────────────────────────────────
                if active_filter != "All":
                    cfg = TIER_CONFIG[active_filter]
                    tier_annual = sum(c.get('annual_qty', 0) for c in filtered)
                    tier_share  = round(100 * tier_annual / total_annual, 1) if total_annual > 0 else 0
                    st.markdown(f'''
<div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px;margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="font-size:0.95rem;font-weight:700;color:{cfg["color"]};">{cfg["icon"]} {active_filter}</span>
    <span style="font-size:0.75rem;color:rgba(255,255,255,0.35);">({len(filtered)} customers)</span>
  </div>
  <span style="font-size:0.75rem;color:rgba(255,255,255,0.45);">
    {tier_annual:,.0f} units/yr · <b style="color:{cfg['color']};">{tier_share}%</b> share
  </span>
</div>
                    ''', unsafe_allow_html=True)

                # ── Pagination ────────────────────────────────────────────────
                total_pages = max(1, -(-len(filtered) // PER_PAGE))  # ceil div
                page = min(st.session_state.tier_page, total_pages - 1)
                start = page * PER_PAGE
                page_items = filtered[start:start + PER_PAGE]

                # ── Render customer cards for this page ───────────────────────
                for c in page_items:
                    tier_name = c['tier']
                    cfg = TIER_CONFIG[tier_name]
                    annual   = c.get('annual_qty', 0)
                    monthly  = c.get('avg_monthly_units', 0)
                    pattern  = c.get('buying_pattern', 'N/A')
                    n_anom   = len(c.get('anomalies', []))
                    share    = round(100 * annual / total_annual, 1) if total_annual > 0 else 0
                    score    = c['composite_score']
                    active   = c.get('active_months', 0)
                    total_mo = c.get('total_months', 1) or 1
                    consist  = round(100 * active / total_mo)
                    dwell    = c.get('avg_dwell_time', None)
                    doc_max  = c.get('doc_consignment_max', None)

                    vs = c['vol_score']
                    cs = c['consist_score']
                    as_ = c['anom_score']
                    ads = c['adhere_score']

                    bar_color = "#22c55e" if consist >= 80 else ("#facc15" if consist >= 50 else "#ef4444")

                    # Cross-product badges
                    xp = cross_product_map.get(c['customer'], [])
                    xp_html = ""
                    if xp:
                        xp_badges = []
                        for xref in xp:
                            xp_cfg = TIER_CONFIG.get(xref['tier'], TIER_CONFIG['Maintain'])
                            xp_badges.append(
                                f'<span style="background:rgba(255,255,255,0.05);'
                                f'color:{xp_cfg["color"]};padding:1px 6px;border-radius:6px;'
                                f'font-size:0.6rem;font-weight:600;border:1px solid {xp_cfg["color"]}30;">'
                                f'{xref["product"]}: {xref["tier"]}'
                                f'</span>'
                            )
                        xp_html = (
                            f'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:6px;">'
                            f'<span style="font-size:0.6rem;color:rgba(255,255,255,0.3);">Also:</span>'
                            f'{"".join(xp_badges)}</div>'
                        )

                    # Anomaly badge
                    anom_html = ""
                    if n_anom > 0:
                        anom_html = (f'<span style="background:rgba(239,68,68,0.12);color:#ef4444;'
                                     f'padding:2px 7px;border-radius:8px;font-size:0.65rem;'
                                     f'font-weight:600;">{n_anom} anomal{"y" if n_anom == 1 else "ies"}</span>')

                    # Dwell adherence badge
                    dwell_html = ""
                    if isinstance(dwell, (int, float)) and isinstance(doc_max, (int, float)) and doc_max > 0:
                        ratio = dwell / doc_max
                        if ratio > 1.5:
                            dwell_html = (f'<span style="background:rgba(239,68,68,0.12);color:#ef4444;'
                                         f'padding:2px 7px;border-radius:8px;font-size:0.65rem;'
                                         f'font-weight:600;">⏱ Dwell {dwell:.0f}d vs {doc_max:.0f}d max</span>')
                        elif ratio > 1.0:
                            dwell_html = (f'<span style="background:rgba(250,204,21,0.12);color:#facc15;'
                                         f'padding:2px 7px;border-radius:8px;font-size:0.65rem;'
                                         f'font-weight:600;">⏱ Dwell {dwell:.0f}d / {doc_max:.0f}d</span>')

                    # Action recommendation for Monitor / Deprioritize
                    action_html = ""
                    if tier_name == "Monitor":
                        if n_anom > 2:
                            action_html = '<div style="font-size:0.72rem;color:rgba(250,204,21,0.7);font-style:italic;margin-top:4px;">💡 Investigate anomaly root cause; consider contract renegotiation</div>'
                        elif isinstance(dwell, (int, float)) and isinstance(doc_max, (int, float)) and dwell > doc_max * 1.5:
                            action_html = f'<div style="font-size:0.72rem;color:rgba(250,204,21,0.7);font-style:italic;margin-top:4px;">💡 Dwell {dwell:.0f}d exceeds contract {doc_max:.0f}d — enforce return terms or renegotiate</div>'
                        else:
                            action_html = '<div style="font-size:0.72rem;color:rgba(250,204,21,0.7);font-style:italic;margin-top:4px;">💡 Low volume or inconsistent — review for potential upgrade or MOQ requirement</div>'
                    elif tier_name == "Deprioritize":
                        if annual < 5:
                            action_html = '<div style="font-size:0.72rem;color:rgba(239,68,68,0.7);font-style:italic;margin-top:4px;">💡 Ghost account — not worth container allocation; consider removal</div>'
                        elif annual < 20:
                            action_html = f'<div style="font-size:0.72rem;color:rgba(239,68,68,0.7);font-style:italic;margin-top:4px;">💡 Fleet costs exceed revenue at {annual} units/yr — set MOQ or consolidate</div>'
                        else:
                            action_html = '<div style="font-size:0.72rem;color:rgba(239,68,68,0.7);font-style:italic;margin-top:4px;">💡 Sporadic demand with low consistency — reallocate fleet resources to Strategic accounts</div>'

                    st.markdown(f'''
<div style="background:{cfg["bg"]};border:1px solid {cfg["border"]}20;
            border-left:4px solid {cfg["border"]};border-radius:10px;
            padding:10px 14px;margin-bottom:6px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div style="display:flex;align-items:center;gap:6px;">
      <span style="font-weight:700;font-size:0.92rem;color:white;">{c['customer']}</span>
      <span style="background:rgba(255,255,255,0.06);color:{cfg['color']};
                   padding:2px 8px;border-radius:8px;font-size:0.65rem;
                   font-weight:700;">{cfg['icon']} {tier_name}</span>
    </div>
    <span style="font-size:0.7rem;color:rgba(255,255,255,0.35);font-weight:600;"
          title="Vol {vs:.0f} · Con {cs:.0f} · Anom {as_:.0f} · Adh {ads:.0f}">
      Score: <b style="color:{cfg['color']};">{score}</b>
    </span>
  </div>
  <div style="display:flex;gap:14px;flex-wrap:wrap;margin:6px 0;">
    <div>
      <div style="font-size:0.58rem;color:rgba(255,255,255,0.35);text-transform:uppercase;">Monthly</div>
      <div style="font-size:0.95rem;font-weight:700;color:#facc15;">{monthly:,.0f}</div>
    </div>
    <div>
      <div style="font-size:0.58rem;color:rgba(255,255,255,0.35);text-transform:uppercase;">Annual</div>
      <div style="font-size:0.95rem;font-weight:700;color:white;">{annual:,.0f}</div>
    </div>
    <div>
      <div style="font-size:0.58rem;color:rgba(255,255,255,0.35);text-transform:uppercase;">Share</div>
      <div style="font-size:0.95rem;font-weight:700;color:#38bdf8;">{share}%</div>
    </div>
    <div>
      <div style="font-size:0.58rem;color:rgba(255,255,255,0.35);text-transform:uppercase;">Pattern</div>
      <div style="font-size:0.78rem;font-weight:600;color:rgba(255,255,255,0.7);">{pattern}</div>
    </div>
    <div style="flex:1;min-width:80px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
        <span style="font-size:0.58rem;color:rgba(255,255,255,0.35);">Consistency</span>
        <span style="font-size:0.58rem;color:{bar_color};font-weight:600;">{consist}%</span>
      </div>
      <div style="background:rgba(255,255,255,0.06);border-radius:3px;height:5px;overflow:hidden;">
        <div style="background:{bar_color};width:{consist}%;height:100%;border-radius:3px;"></div>
      </div>
    </div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
    {anom_html}{dwell_html}
  </div>
  {xp_html}
  {action_html}
</div>
                    ''', unsafe_allow_html=True)

                # ── Pagination controls ───────────────────────────────────────
                if total_pages > 1:
                    _pprev, _pinfo, _pnext = st.columns([1, 2, 1])
                    with _pprev:
                        if st.button("‹ Prev", disabled=(page == 0),
                                     use_container_width=True, key="tier_prev"):
                            st.session_state.tier_page = max(0, page - 1)
                            st.rerun()
                    with _pinfo:
                        st.markdown(
                            f'<div style="text-align:center;padding:6px 0;font-size:0.82rem;'
                            f'color:rgba(255,255,255,0.5);">'
                            f'Page <b style="color:white;">{page + 1}</b> of {total_pages} '
                            f'<span style="color:rgba(255,255,255,0.3);">·</span> '
                            f'{len(filtered)} customers</div>',
                            unsafe_allow_html=True
                        )
                    with _pnext:
                        if st.button("Next ›", disabled=(page >= total_pages - 1),
                                     use_container_width=True, key="tier_next"):
                            st.session_state.tier_page = min(total_pages - 1, page + 1)
                            st.rerun()

            # ── Cross-Product Summary (collapsible) ───────────────────────────
            multi_custs = [c for c in tiered if c['customer'] in cross_product_map]
            if multi_custs:
                with st.expander(f"🔗 Cross-Product Summary ({len(multi_custs)} multi-product customers)", expanded=False):
                    for mc in multi_custs:
                        xp = cross_product_map.get(mc['customer'], [])
                        total_vol = mc.get('annual_qty', 0) + sum(x['annual'] for x in xp)
                        if total_vol > 0:
                            w_score = (mc['composite_score'] * mc.get('annual_qty', 0) +
                                       sum(x['score'] * x['annual'] for x in xp)) / total_vol
                        else:
                            w_score = mc['composite_score']

                        if w_score >= 75:
                            c_tier = "Strategic"
                        elif w_score >= 55:
                            c_tier = "Growth"
                        elif w_score >= 35:
                            c_tier = "Maintain"
                        elif w_score >= 18:
                            c_tier = "Monitor"
                        else:
                            c_tier = "Deprioritize"

                        c_cfg = TIER_CONFIG[c_tier]

                        prod_tags = (
                            f'<span style="background:rgba(255,255,255,0.05);color:{TIER_CONFIG[mc["tier"]]["color"]};'
                            f'padding:1px 6px;border-radius:6px;font-size:0.62rem;font-weight:600;'
                            f'border:1px solid {TIER_CONFIG[mc["tier"]]["color"]}25;">'
                            f'{selected_item}: {mc["tier"]} ({mc["composite_score"]})</span>'
                        )
                        for x in xp:
                            x_cfg = TIER_CONFIG.get(x['tier'], TIER_CONFIG['Maintain'])
                            prod_tags += (
                                f' <span style="background:rgba(255,255,255,0.05);color:{x_cfg["color"]};'
                                f'padding:1px 6px;border-radius:6px;font-size:0.62rem;font-weight:600;'
                                f'border:1px solid {x_cfg["color"]}25;">'
                                f'{x["product"]}: {x["tier"]} ({x["score"]})</span>'
                            )

                        st.markdown(f'''
<div style="background:rgba(30,32,40,0.4);border:1px solid rgba(255,255,255,0.06);
            border-left:4px solid {c_cfg["border"]};border-radius:10px;
            padding:10px 14px;margin-bottom:6px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div style="display:flex;align-items:center;gap:6px;">
      <span style="font-weight:700;font-size:0.9rem;color:white;">{mc['customer']}</span>
      <span style="background:rgba(255,255,255,0.06);color:{c_cfg['color']};
                   padding:2px 8px;border-radius:8px;font-size:0.65rem;
                   font-weight:700;">Overall: {c_tier}</span>
    </div>
    <span style="font-size:0.7rem;color:rgba(255,255,255,0.4);">
      Weighted Score: <b style="color:{c_cfg['color']};">{w_score:.1f}</b>
    </span>
  </div>
  <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;">
    {prod_tags}
  </div>
</div>
                        ''', unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        customer_options = [r['customer'] for r in item_insights]
        st.selectbox(
            "🔍 Select Customer for Deep Dive",
            options=customer_options,
            key='deep_dive',
            index=None,
            placeholder="Type to search customers..."
        )
    # ── RIGHT COLUMN: Simulation Parameters + Run ─────────────────────────────
    with _ctrl_right:
        # Möbius GIF header
        @st.cache_data(show_spinner=False)
        def _load_gif_b64(path: str) -> str:
            try:
                with open(path, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
            except FileNotFoundError:
                return ''

        st.markdown("#### ⚙️ Simulation Parameters")

        daily_demand = st.number_input(
            "Daily Demand",
            min_value=0.0,
            value=float(item_demand),
            step=0.1,
            format="%.1f",
            help="Average units shipped per day.",
            key="fo_demand",
        )
        if 0 < daily_demand < 1.0:
            st.caption(f"ℹ️ Fractional demand: ~1 unit every {1/daily_demand:.1f} days")

        customer_dwell_mean = st.slider(
            "Average Dwell Time (Days)",
            min_value=1, max_value=365,
            value=int(item_dwell), step=1,
            key="fo_dwell",
        )
        target_availability = st.slider(
            "Target Availability",
            min_value=0.90, max_value=0.99,
            value=0.99, step=0.01,
            format="%.2f",
            key="fo_avail",
        )
        eu_exposure = st.slider(
            "EU Market Exposure (%)",
            min_value=0, max_value=100,
            value=20, step=1,
            key="fo_eu",
        )
        auto_replenish = st.toggle("🛒 Auto-Replenish (Purchase New)", value=False, key="fo_replenish")

        st.caption(
            f"**{selected_item}** real-world data:\n\n"
            f"- Avg Daily Demand: `{item_demand}`\n"
            f"- Avg Dwell Time: `{item_dwell}` days\n"
            f"- Known Fleet Size: `{item_fleet_size}` assets"
        )

        run_btn = st.button("▶ Run Simulation", type="primary", use_container_width=True, key="fo_run")

        # AI key disconnect
        if st.session_state.get('gemini_key'):
            if st.button("🔑 Disconnect AI", use_container_width=True, key="fo_disconnect_ai"):
                del st.session_state['gemini_key']
                st.rerun()

    st.divider()

    # ── Simulation results ────────────────────────────────────────────────────

    st.markdown(
        "Adjust parameters above and click **▶ Run Simulation** "
        "to find the optimal fleet size."
    )

    if run_btn:
        with st.spinner("Simulating fleet dynamics and calculating optimal size..."):
            optimal_fleet_size, sim_fig, availability_thresholds = run_simulation(
                item_name           = selected_item,
                daily_demand        = daily_demand,
                customer_dwell_mean = customer_dwell_mean,
                target_availability = target_availability,
                eu_exposure_percent = eu_exposure / 100.0,
                auto_replenish      = auto_replenish
            )
            # Persist results in session state so they survive sidebar interactions
            st.session_state['sim_fig']             = sim_fig
            st.session_state['optimal_fleet_size']  = optimal_fleet_size
            st.session_state['sim_daily_demand']    = daily_demand
            st.session_state['sim_eu_exposure']     = eu_exposure
            st.session_state['availability_thresholds'] = availability_thresholds

    # Render simulation results if a run has been performed
    if 'sim_fig' in st.session_state:
        col_fleet, col_demand, col_eu = st.columns(3)

        # Build a tooltip showing fleet sizes at alternative availability levels
        thresholds      = st.session_state.get('availability_thresholds', {})
        tooltip_lines   = "<br>".join(
            f"{level*100:.0f}% avail: {size:,} assets"
            for level, size in thresholds.items()
            if level != target_availability
        )
        fleet_tooltip_html = f"""
        <div class="tooltip" style="border-bottom:1px dashed #4e9af1;width:fit-content;">
            <span style="font-size:2rem;font-weight:bold;color:#0052cc;">
                {st.session_state['optimal_fleet_size']:,}
            </span>
            <span class="tooltiptext">Tradeoffs:<br>{tooltip_lines}</span>
        </div>
        """

        with col_fleet:
            st.caption("Optimal Fleet Size")
            st.markdown(fleet_tooltip_html, unsafe_allow_html=True)
            st.caption(f"vs known: {st.session_state['optimal_fleet_size'] - item_fleet_size:+,}")

        col_demand.metric("Daily Demand Used", str(st.session_state['sim_daily_demand']))
        col_eu.metric("EU Exposure",           f"{st.session_state['sim_eu_exposure']}%")

        # Adjust chart height based on whether the deep-dive panel is also visible
        chart_height = 400 if st.session_state.get('deep_dive') else 500
        st.session_state['sim_fig'].update_layout(height=chart_height)
        st.plotly_chart(st.session_state['sim_fig'], use_container_width=True, config={'displayModeBar': False})


    # ── 10. Customer deep-dive panel ──────────────────────────────────────────────
    # Rendered independently of the simulation button so it persists between runs.

    @st.cache_data(show_spinner=False)
    def run_micro_simulation(item, d_demand, d_dwell):
        return run_simulation(
            item_name=item,
            daily_demand=d_demand,
            customer_dwell_mean=d_dwell,
            target_availability=0.99,
            eu_exposure_percent=0.0  # Skip EU replacement for micro-sim to gain speed
        )

    selected_customer = st.session_state.get('deep_dive')
    if selected_customer:
        st.subheader(f"Deep Dive: {selected_customer}")
        cust_data = next((r for r in item_insights if r['customer'] == selected_customer), None)

        if cust_data:
            # ── Extract key metrics ──────────────────────────────────────────────
            annual_demand   = cust_data.get('annual_qty', 0)
            actual_dwell    = cust_data.get('avg_dwell_time', 'N/A')
            contracted_time = cust_data.get('doc_total_time', 'N/A')

            dwell_display      = f"{actual_dwell} days"    if isinstance(actual_dwell,    (int, float)) else "N/A"
            contracted_display = f"{contracted_time} days" if isinstance(contracted_time, (int, float)) else "N/A"

            # Dwell variance: positive means retaining assets longer than contracted
            if isinstance(actual_dwell, (int, float)) and isinstance(contracted_time, (int, float)):
                variance_days  = round(actual_dwell - contracted_time, 1)
                variance_label = f"{variance_days:+} days"
            else:
                variance_days  = None
                variance_label = "N/A"

            # Order history as a flat list of quantities (used for sparklines)
            hist_quantities = [h['qty'] for h in cust_data.get('history', [])] if 'history' in cust_data else []

            # 3-state health system for Dwell Variance
            #   Positive → customer over-retaining assets (BAD)  → red
            #   Negative → returning faster than contracted (GOOD) → green
            #   Zero/N/A → on-track                               → yellow
            if variance_days is not None and variance_days > 1:
                variance_color      = '#ff4b4b'   # red
                variance_arrow      = '↑'
                variance_health_dot = '🔴'
                variance_sparkline_color = '#ff4b4b'
            elif variance_days is not None and variance_days < -1:
                variance_color      = '#22c55e'   # green
                variance_arrow      = '↓'
                variance_health_dot = '🟢'
                variance_sparkline_color = '#22c55e'
            else:
                variance_color      = '#facc15'   # yellow
                variance_arrow      = '→'
                variance_health_dot = '🟡'
                variance_sparkline_color = '#facc15'

            variance_delta_html = (
                f'<span style="font-size:0.8rem;color:{variance_color};margin-top:2px;display:block;">'
                f'{variance_arrow} {variance_label}</span>'
                if variance_days is not None else ''
            )

            DISPLAYMODEBAROFF = {'displayModeBar': False}

            # ── Metric cards (4 columns) ──────────────────────────────────────────
            m1, m2, m3, m4 = st.columns(4)

            with m1:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:0.78rem;opacity:0.65;margin-bottom:2px;">Annual Demand</div>'
                        f'<div style="font-size:2rem;font-weight:700;color:white;line-height:1.1;">{annual_demand:,}</div>',
                        unsafe_allow_html=True
                    )
                    if len(hist_quantities) > 2:
                        st.plotly_chart(make_sparkline(hist_quantities, '#0052cc'), use_container_width=True, config=DISPLAYMODEBAROFF)

            with m2:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:0.78rem;opacity:0.65;margin-bottom:2px;">Actual Dwell Time</div>'
                        f'<div style="font-size:2rem;font-weight:700;color:white;line-height:1.1;">{dwell_display}</div>',
                        unsafe_allow_html=True
                    )
                    if len(hist_quantities) > 2:
                        flat_dwell = [actual_dwell] * len(hist_quantities)
                        st.plotly_chart(make_sparkline(flat_dwell, '#ffaa00'), use_container_width=True, config=DISPLAYMODEBAROFF)

            with m3:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:0.78rem;opacity:0.65;margin-bottom:2px;">Documented Loop Time</div>'
                        f'<div style="font-size:2rem;font-weight:700;color:white;line-height:1.1;">{contracted_display}</div>',
                        unsafe_allow_html=True
                    )
                    if len(hist_quantities) > 2:
                        flat_contracted = [contracted_time] * len(hist_quantities)
                        st.plotly_chart(make_sparkline(flat_contracted, 'rgba(200,200,200,0.6)'), use_container_width=True, config=DISPLAYMODEBAROFF)

            with m4:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="font-size:0.78rem;opacity:0.65;margin-bottom:2px;">'
                        f'Dwell Variance &nbsp;{variance_health_dot}</div>'
                        f'<div style="font-size:2rem;font-weight:700;color:{variance_color};line-height:1.1;">'
                        f'{variance_label}</div>'
                        f'{variance_delta_html}',
                        unsafe_allow_html=True
                    )
                    if len(hist_quantities) > 2 and variance_days is not None:
                        flat_variance = [variance_days] * len(hist_quantities)
                        st.plotly_chart(make_sparkline(flat_variance, variance_sparkline_color), use_container_width=True, config=DISPLAYMODEBAROFF)

            st.divider()

            st.markdown(f"### 🎯 Customer-Level Micro Simulation")
            st.caption(f"Predicts dedicated fleet requirements for **{selected_customer}** using their specific demand profile and dwell time.")

            with st.spinner(f"Running micro-simulation for {selected_customer}..."):
                # Derive daily volume from expected annual shipments
                c_demand = max(0.1, annual_demand / 365.25)
                # Use actual dwell if valid, otherwise let simulation use item defaults
                c_dwell  = actual_dwell if isinstance(actual_dwell, (int, float)) else None

                c_fleet, c_fig, c_thresh = run_micro_simulation(selected_item, c_demand, c_dwell)

                # Rebrand chart specifically for this customer
                c_fig.update_layout(
                    title=f"<b>Fleet Capacity vs. Availability ({selected_customer})</b>",
                    height=350,
                    margin=dict(l=0, r=0, t=50, b=0)
                )

                mc_col1, mc_col2 = st.columns([1, 4])
                with mc_col1:
                    st.metric("Optimal Fleet Allocation", c_fleet, help="Assets needed to hit 99% fulfillment rate")
                    st.metric("Daily Demand Profile", f"{c_demand:.1f}", help="Calculated from annual volume")
                    st.metric("Simulation Dwell", dwell_display, help="Actual historical dwell used in model")
                with mc_col2:
                    st.plotly_chart(c_fig, use_container_width=True, config=DISPLAYMODEBAROFF)

            st.divider()

            # ── Anomaly watchdog ──────────────────────────────────────────────────
            anomalies_list = cust_data.get('anomalies', [])
            if anomalies_list:
                already_archived  = get_archived_ids()

                # Split into unresolved (need attention) vs resolved (already archived)
                unresolved = [
                    a for a in anomalies_list
                    if f"{selected_customer}__{selected_item}__{a['date']}".lower().replace(" ", "_")
                       not in already_archived
                ]

                # ── Banner: only red when there are still unresolved anomalies ────
                if unresolved:
                    st.error(
                        f"🚨 **Demand Anomaly Detected!** "
                        f"This customer has **{len(unresolved)}** unresolved order spike(s) "
                        f"requiring classification."
                    )
                else:
                    st.success(
                        f"✅ **All anomalies resolved.** "
                        f"All {len(anomalies_list)} detected spike(s) have been classified. "
                        f"See **📁 Archive History** below to review them."
                    )

                # ── Triage Panel: only shown when there are unresolved anomalies ──
                if unresolved:
                    with st.expander("🗂️ Classify & Archive Anomalies", expanded=True):
                        st.caption(
                            "Check each anomaly, choose a reason, add optional notes, "
                            "then click **Save to Archive**. Archived events will be removed from this panel."
                        )

                        # Column headers
                        h0, h1, h2, h3, h4, h5 = st.columns([0.5, 1.5, 1, 1, 2.5, 3])
                        h0.markdown("**✓**")
                        h1.markdown("**Date**")
                        h2.markdown("**Qty**")
                        h3.markdown("**Z-Score**")
                        h4.markdown("**Reason**")
                        h5.markdown("**Notes**")
                        st.divider()

                        # One row per UNRESOLVED anomaly only
                        triage_state = []
                        for anom in unresolved:
                            anom_id = f"{selected_customer}__{selected_item}__{anom['date']}".lower().replace(" ", "_")
                            c0, c1, c2, c3, c4, c5 = st.columns([0.5, 1.5, 1, 1, 2.5, 3])

                            checked = c0.checkbox(label="", key=f"chk_{anom_id}")
                            c1.write(anom['date'])
                            c2.write(f"{anom['qty']:,}")
                            c3.write(f"{anom['z_score']:.2f}")
                            reason = c4.selectbox(
                                label="", options=ANOMALY_REASONS,
                                key=f"rsn_{anom_id}", label_visibility="collapsed"
                            )
                            notes = c5.text_input(
                                label="", placeholder="Optional notes…",
                                key=f"nts_{anom_id}", label_visibility="collapsed"
                            )
                            triage_state.append({
                                "checked": checked, "reason": reason,
                                "notes": notes, "anom": anom,
                            })

                        # Right-aligned Save button
                        pending = [t for t in triage_state if t['checked'] and t['reason'] != ANOMALY_REASONS[0]]
                        _spacer, _btn_col = st.columns([7, 3])
                        if _btn_col.button("💾 Save to Archive", type="primary", use_container_width=True, key=f"archive_btn_{selected_customer}"):
                            if not pending:
                                st.warning("Check at least one anomaly and choose a reason before saving.")
                            else:
                                new_entries = [
                                    build_archive_entry(
                                        customer = selected_customer,
                                        item     = selected_item,
                                        date     = t['anom']['date'],
                                        qty      = t['anom']['qty'],
                                        z_score  = t['anom']['z_score'],
                                        reason   = t['reason'],
                                        notes    = t['notes'],
                                    )
                                    for t in pending
                                ]
                                added, skipped = archive_anomalies(new_entries)
                                if added:
                                    st.success(f"✅ {added} anomaly{'s' if added > 1 else ''} archived and removed from the watchdog.")
                                if skipped:
                                    st.info(f"ℹ️ {skipped} already archived — skipped.")
                                st.rerun()  # Immediately removes resolved rows from the watchdog panel
                # ── Archive History Viewer ────────────────────────────────────────
                all_archived = load_archive()
                # Filter to only show archive entries relevant to this customer + item
                cust_archive = [
                    e for e in all_archived
                    if e.get('customer') == selected_customer and e.get('item') == selected_item
                ]
                if cust_archive:
                    with st.expander(f"📁 Archive History ({len(cust_archive)} resolved)"):
                        df_archive = pd.DataFrame(cust_archive)[[
                            'date', 'qty', 'z_score', 'reason', 'notes', 'archived_at'
                        ]]
                        df_archive.columns = ['Date', 'Qty', 'Z-Score', 'Reason', 'Notes', 'Archived At']
                        st.dataframe(df_archive, hide_index=True, use_container_width=True)

                        # Download the full archive as CSV
                        csv_archive = df_archive.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="⬇️ Export Archive CSV",
                            data=csv_archive,
                            file_name=f"{selected_customer.replace(' ', '_')}_anomaly_archive.csv",
                            mime="text/csv",
                            key=f"dl_archive_{selected_customer}"
                        )

            # ── AI dwell insight ──────────────────────────────────────────────────
            status, insight_text = generate_dwell_insight(actual_dwell, contracted_time)
            if   status == 'warning': st.warning(insight_text, icon="🤖")
            elif status == 'success': st.success(insight_text, icon="✨")
            elif status == 'info':    st.info(insight_text,    icon="🧠")
            else:                     st.error(insight_text,   icon="⚠️")

            # ── Contract & logistics assumptions expander ─────────────────────────
            with st.expander("📄 View Contract & Logistics Assumptions"):
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    st.markdown("**Inventory Rules**")
                    st.write(f"- **Consignment Max:** `{cust_data.get('doc_consignment_max', 'N/A')}`")
                    st.write(f"- **Daily Consumption:** `{cust_data.get('doc_daily_consumption', 'N/A')}`")
                with exp_col2:
                    st.markdown("**Logistics Breakdown (Days)**")
                    st.write(f"- **Transit OUT (to customer):** `{cust_data.get('doc_transit_out', 'N/A')}`")
                    st.write(f"- **Transit IN (to MLI):** `{cust_data.get('doc_transit_in', 'N/A')}`")
                    st.write(f"- **Other Touch Points:** `{cust_data.get('doc_touch_points', 'N/A')}`")

            st.divider()

            # ── Order history: advanced forecast chart + raw table ────────────────
            if 'history' in cust_data:
                df_history = pd.DataFrame(cust_data['history'])
                if not df_history.empty:
                    df_history.columns = ['Date', 'Quantity']

                    df_ts           = df_history.copy()
                    df_ts['Date']   = pd.to_datetime(df_ts['Date'])
                    df_ts           = df_ts.groupby('Date')['Quantity'].sum().reset_index()

                    if len(df_ts) > 3:
                        # ── EWMA Trend smoothing ──────────────────────────────────
                        # Span=5 gives more weight to recent months while smoothing noise
                        df_ts['EWMA_Trend'] = df_ts['Quantity'].ewm(span=5, adjust=False).mean()

                        # ── 90-day stochastic mean-reverting forecast ─────────────
                        # The future walk starts at the last EWMA value and adds small
                        # Gaussian noise scaled to 15% of historical std dev.
                        last_date      = df_ts['Date'].max()
                        future_dates   = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=90)
                        hist_std       = df_ts['Quantity'].std()
                        last_trend_val = df_ts['EWMA_Trend'].iloc[-1]

                        np.random.seed(42)  # Fixed seed for reproducible dashboard renders
                        future_quantities = []
                        current_val = last_trend_val
                        for _ in range(90):
                            noise       = np.random.normal(0, hist_std * 0.15)
                            current_val = max(0, current_val + noise)
                            future_quantities.append(current_val)

                        # ── Confidence interval band ──────────────────────────────
                        upper_bound = [v + hist_std * 0.8 for v in future_quantities]
                        lower_bound = [max(0, v - hist_std * 0.8) for v in future_quantities]

                        fig_forecast = go.Figure()

                        # 1. Historical volume bars
                        fig_forecast.add_trace(go.Bar(
                            x=df_ts['Date'], y=df_ts['Quantity'],
                            name='Historical Volume',
                            marker_color='rgba(250,250,250,0.1)'
                        ))
                        # 2. EWMA smoothing trend line
                        fig_forecast.add_trace(go.Scatter(
                            x=df_ts['Date'], y=df_ts['EWMA_Trend'],
                            name='EWMA Smoothing Trend', mode='lines',
                            line=dict(color='#ffaa00', width=3, shape='spline')
                        ))
                        # 3. 90-day projected forecast line
                        fig_forecast.add_trace(go.Scatter(
                            x=future_dates, y=future_quantities,
                            name='90-Day Predictive Forecast', mode='lines',
                            line=dict(color='#0052cc', width=4, dash='dot', shape='spline')
                        ))
                        # 4. Confidence interval shaded area
                        fig_forecast.add_trace(go.Scatter(
                            x=future_dates.tolist() + future_dates.tolist()[::-1],
                            y=upper_bound + lower_bound[::-1],
                            fill='toself',
                            fillcolor='rgba(0,82,204,0.15)',
                            line=dict(color='rgba(255,255,255,0)'),
                            name='90% Confidence Interval',
                            showlegend=True
                        ))

                        fig_forecast.update_layout(
                            title="<b>📈 Advanced Demand Forecasting & Projection</b>",
                            hovermode="x unified",
                            height=450,
                            plot_bgcolor='rgba(38,39,48,1)',
                            paper_bgcolor='rgba(38,39,48,1)',
                            margin=dict(l=0, r=0, t=60, b=80),
                            legend=dict(
                                orientation="h", yanchor="top", y=-0.15,
                                xanchor="center", x=0.5,
                                bgcolor='rgba(38,39,48,0)',
                                font=dict(color='rgba(255,255,255,0.7)')
                            )
                        )
                        fig_forecast.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)',
                                                  color='rgba(255,255,255,0.5)', zeroline=False)
                        fig_forecast.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)',
                                                  color='rgba(255,255,255,0.5)', zeroline=False)

                        st.plotly_chart(fig_forecast, use_container_width=True)

                    # Raw history table and CSV download
                    st.dataframe(df_history, hide_index=True, width='stretch')
                    csv_bytes = df_history.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"⬇️ Download {selected_customer} Audit CSV",
                        data=csv_bytes,
                        file_name=f"{selected_customer.replace(' ', '_')}_Audit.csv",
                        mime="text/csv"
                    )
                else:
                    st.caption("No order history available.")





