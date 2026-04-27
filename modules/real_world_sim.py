"""
pages/real_world_sim.py
-----------------------
Supply Chain Command Center — Real-time fleet intelligence dashboard.

Renders:
  - EWMA sync & date-filtered metrics (Volume, Velocity, Freshness, R2R)
  - What-If Simulator (demand surge / logistics delay)
  - Cumulative volume chart + daily shipment bars
  - Live order feed (20 most recent)
  - Fleet return tracking: Sankey diagram, compliance cards, age histogram
  - ASU footer
"""
from __future__ import annotations

import os
import base64
import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ewma_sync import sync_to_now
from mfg_generator import sync_mfg_data
from return_tracker import get_fleet_status

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render():
    """Render the Real World Simulation page."""
    # ── Sync data to current date (EWMA gap fill) ─────────────────────────
    _sync_result = sync_to_now()
    if _sync_result.get("status") == "synced":
        st.toast(f"📡 Synced +{_sync_result['rows_added']} rows to {_sync_result['new_max']}", icon="✅")
        st.cache_data.clear()

    # ── Page-level CSS ────────────────────────────────────────────────────
    st.markdown('''
    <style>
    .block-container { padding-top: 2rem !important; max-width: 1400px !important; }

    /* Glassmorphism metric card */
    .sim-card {
        background: rgba(30, 32, 40, 0.55);
        backdrop-filter: blur(24px) saturate(160%);
        -webkit-backdrop-filter: blur(24px) saturate(160%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 22px 24px;
        margin-bottom: 16px;
        transition: all 0.3s ease;
    }
    .sim-card:hover {
        transform: translateY(-3px);
        border-color: rgba(255,255,255,0.18);
        box-shadow: 0 12px 36px rgba(0,0,0,0.35);
    }
    .sim-card .card-label {
        font-size: 0.78rem;
        color: rgba(255,255,255,0.55);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .sim-card .card-value {
        font-size: 2.6rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .sim-card .card-delta {
        font-size: 0.82rem;
        margin-top: 2px;
    }
    .sim-card .card-sub {
        font-size: 0.72rem;
        color: rgba(255,255,255,0.35);
        margin-top: 4px;
    }
    .delta-up   { color: #22c55e; }
    .delta-down { color: #ff4b4b; }
    .delta-flat { color: #facc15; }

    /* Amber row highlighting for the live feed */
    .amber-row { background: rgba(250, 204, 21, 0.12) !important; }

    /* Section title */
    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: rgba(255,255,255,0.85);
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }

    /* Filter bar */
    .filter-bar {
        background: rgba(30, 32, 40, 0.4);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 12px 20px;
        margin-bottom: 20px;
    }
    </style>
    ''', unsafe_allow_html=True)


    # ── Page header ───────────────────────────────────────────────────────
    st.markdown('''
    <div style="margin-bottom:28px;">
        <h1 style="font-size:2.4rem;font-weight:800;margin:0 0 4px;
                   background:linear-gradient(135deg,#ffffff 0%,#a0aec0 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            💰 Supply Chain Command Center
        </h1>
        <p style="color:#8892b0;font-size:1rem;margin:0;">
            Real-time fleet intelligence powered by FINAL_ data files &nbsp;·&nbsp; Auto-synced with pipeline
        </p>
    </div>
    ''', unsafe_allow_html=True)

    # ── Load live data from FINAL CSVs ────────────────────────────────────
    # _BASE defined at module level

    @st.cache_data(show_spinner=False)
    def _load_sim_data(_ts: float):
        """Load all FINAL CSVs. _ts is mtime for cache invalidation."""
        sales = pd.read_csv(os.path.join(_BASE, "FINAL_Sales_QTY.csv"), parse_dates=["Date"])
        loops = pd.read_csv(os.path.join(_BASE, "FINAL_Documented_Loop_Times.csv"))
        r2r   = pd.read_csv(os.path.join(_BASE, "FINAL_Receipt_to_Receipt_Data.csv"))

        # Auto-generate MFG records for products in Sales but missing from MFG
        mfg = sync_mfg_data(
            sales_path=os.path.join(_BASE, "FINAL_Sales_QTY.csv"),
            mfg_path=os.path.join(_BASE, "FINAL_MFG_Date.csv"),
        )
        return sales, loops, mfg, r2r

    # Use FINAL CSV mtime as cache key (sync_to_now writes here)
    try:
        _sim_mtime = os.path.getmtime(os.path.join(_BASE, "FINAL_Sales_QTY.csv"))
    except FileNotFoundError:
        _sim_mtime = 0

    try:
        df_sales, df_loops, df_mfg, df_r2r = _load_sim_data(_sim_mtime)
    except Exception as e:
        st.error(f"⚠️ **Data loading failed.** Please ensure all FINAL_ CSV files exist in the project directory.\\n\\n`{e}`")
        st.stop()

    # ── Parse item types for filtering ────────────────────────────────────
    def _item_type(label):
        u = str(label).upper()
        if "1000L" in u: return "1000L Tote"
        if "55GAL" in u: return "55GAL Drum"
        if "330GAL" in u: return "330GAL Tote"
        return "Other"

    df_sales["Item Type"] = df_sales["Customer/Product"].apply(_item_type)

    # ── Filter bar (date range + product + customer) ──────────────────────
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([2, 1.5, 2, 1])
    with fc1:
        date_range = st.date_input(
            "📅 Date Range",
            value=(df_sales["Date"].min().date(), df_sales["Date"].max().date()),
            key="rw_date_range"
        )
    with fc2:
        product_opts = ["All"] + sorted(df_sales["Item Type"].unique().tolist())
        sel_product = st.selectbox("📦 Product", product_opts, key="rw_product")
    with fc3:
        # Customer list scoped to the selected product
        _cust_source = df_sales if sel_product == "All" else df_sales[df_sales["Item Type"] == sel_product]
        _cust_names = sorted(_cust_source["Customer/Product"].str.split("(").str[0].str.strip().unique())
        cust_opts = ["All"] + _cust_names
        sel_customer = st.selectbox("👤 Customer", cust_opts, key="rw_customer")
    with fc4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", key="rw_refresh", use_container_width=True):
            st.cache_data.clear()
            for k in ["rw_date_range", "rw_product", "rw_customer", "rw_granularity"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Apply filters ─────────────────────────────────────────────────────
    filtered = df_sales.copy()
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        filtered = filtered[
            (filtered["Date"].dt.date >= date_range[0]) &
            (filtered["Date"].dt.date <= date_range[1])
        ]
    if sel_product != "All":
        filtered = filtered[filtered["Item Type"] == sel_product]
    if sel_customer != "All":
        filtered = filtered[filtered["Customer/Product"].str.startswith(sel_customer)]

    # ── What-If Simulator (collapsible) ───────────────────────────────────
    with st.expander("🎛️ What-If Simulator — Adjust Demand & Logistics", expanded=False):
        sim_c1, sim_c2, sim_c3 = st.columns(3)
        with sim_c1:
            demand_surge = st.slider(
                "Demand Surge (%)", -50, 100, 0, step=5,
                help="Simulate a percentage change in demand volume",
                key="rw_demand_surge"
            )
        with sim_c2:
            logistics_delay = st.slider(
                "Logistics Delay (days)", -10, 30, 0, step=1,
                help="Add/remove days to transit times",
                key="rw_logistics_delay"
            )
        with sim_c3:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if demand_surge != 0 or logistics_delay != 0:
                st.info(f"📊 Simulating: demand **{demand_surge:+d}%**, transit **{logistics_delay:+d}** days")
            else:
                st.caption("Move sliders to see what-if impact on metrics")

    # ── Compute metrics (with what-if adjustments) ────────────────────────
    surge_mult = 1 + (demand_surge / 100.0)

    raw_volume = filtered["Quantity"].sum()
    sim_volume = int(raw_volume * surge_mult)

    # Velocity: match filtered customers to loop data for accurate per-customer transit time
    _loop_names_clean = df_loops["Customer Name"].str.split("(").str[0].str.strip()
    _filtered_custs = filtered["Customer/Product"].str.split("(").str[0].str.strip().unique()
    _matched_loops = df_loops[_loop_names_clean.isin(_filtered_custs)]
    if _matched_loops.empty:
        # Fallback: fleet-wide average if no match found
        raw_velocity = df_loops["Total Transit Time (Days)"].mean()
        _vel_label = "Fleet-wide avg transit time (days)"
    elif sel_customer != "All":
        # Specific customer selected — show their transit time
        raw_velocity = _matched_loops["Total Transit Time (Days)"].mean()
        _vel_label = f"{sel_customer} transit time (days)"
    else:
        raw_velocity = _matched_loops["Total Transit Time (Days)"].mean()
        _vel_label = "Avg transit time for selection (days)"
    sim_velocity = round(raw_velocity + logistics_delay, 1)

    days_since_mfg = (pd.Timestamp.now() - df_mfg["MFG DATE"]).dt.days
    sim_freshness = int(days_since_mfg.mean())

    raw_efficiency = df_r2r["R2R Days (median)"].mean()
    sim_efficiency = round(raw_efficiency + logistics_delay * 0.5, 1)

    # Deltas (vs baseline)
    vol_delta = sim_volume - raw_volume
    vel_delta = sim_velocity - raw_velocity
    eff_delta = sim_efficiency - raw_efficiency

    def _delta_class(val, invert=False):
        if val > 0: return "delta-down" if not invert else "delta-up"
        if val < 0: return "delta-up" if not invert else "delta-down"
        return "delta-flat"

    def _delta_str(val, suffix=""):
        if val > 0: return f"↑ +{val:,.1f}{suffix}"
        if val < 0: return f"↓ {val:,.1f}{suffix}"
        return f"→ baseline"

    # ── Layout: Left metric stack + Right charts (inspired by reference) ──
    left_col, right_col = st.columns([1, 2.8], gap="medium")

    with left_col:
        # Card 1: Volume
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">📦 Total Volume</div>
            <div class="card-value" style="color:#0052cc;">{sim_volume:,}</div>
            <div class="card-delta {_delta_class(vol_delta, invert=True)}">{_delta_str(vol_delta, " units")}</div>
            <div class="card-sub">Sum of all shipped quantity</div>
        </div>
        ''', unsafe_allow_html=True)

        # Card 2: Velocity
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">🚚 Avg Transit Velocity</div>
            <div class="card-value" style="color:#ffaa00;">{sim_velocity}</div>
            <div class="card-delta {_delta_class(vel_delta)}">{_delta_str(vel_delta, " days")}</div>
            <div class="card-sub">{_vel_label}</div>
        </div>
        ''', unsafe_allow_html=True)

        # Card 3: Freshness
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">🏭 Fleet Freshness</div>
            <div class="card-value" style="color:#22c55e;">{sim_freshness:,}</div>
            <div class="card-delta delta-flat">→ avg days since MFG</div>
            <div class="card-sub">Lower = newer fleet assets</div>
        </div>
        ''', unsafe_allow_html=True)

        # Card 4: Efficiency
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">♻️ R2R Efficiency</div>
            <div class="card-value" style="color:#a78bfa;">{sim_efficiency}</div>
            <div class="card-delta {_delta_class(eff_delta)}">{_delta_str(eff_delta, " days")}</div>
            <div class="card-sub">Receipt-to-Receipt median (days)</div>
        </div>
        ''', unsafe_allow_html=True)

    with right_col:
        # ── Main chart: Cumulative sales area + EWMA forecast ────────────
        st.markdown('<div class="section-title">📈 Cumulative Volume vs. EWMA Forecast</div>',
                    unsafe_allow_html=True)

        ts = filtered.groupby("Date")["Quantity"].sum().sort_index().reset_index()

        # Reindex to full date range so x-axis always shows all days
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            _full_dates = pd.date_range(date_range[0], date_range[1], freq="D")
            _full_df = pd.DataFrame({"Date": _full_dates})
            ts = _full_df.merge(ts, on="Date", how="left").fillna({"Quantity": 0})

        ts["Cumulative"] = (ts["Quantity"] * surge_mult).cumsum()

        # EWMA on daily quantity — smooth trend line
        if not ts.empty:
            ts["EWMA"] = (ts["Quantity"] * surge_mult).ewm(span=14, adjust=False).mean()
            # Cumulative EWMA forecast: project the EWMA rate forward
            ts["EWMA_Cumulative"] = ts["EWMA"].cumsum()

        fig_area = go.Figure()
        # Actual cumulative (blue area)
        fig_area.add_trace(go.Scatter(
            x=ts["Date"], y=ts["Cumulative"],
            fill="tozeroy", name="Actual (Cumulative)",
            fillcolor="rgba(0, 82, 204, 0.25)",
            line=dict(color="#0052cc", width=3, shape="spline"),
            hovertemplate="%{x|%b %d}<br>Volume: %{y:,.0f}<extra></extra>"
        ))
        # EWMA cumulative (green line)
        if not ts.empty and "EWMA_Cumulative" in ts.columns:
            fig_area.add_trace(go.Scatter(
                x=ts["Date"], y=ts["EWMA_Cumulative"],
                name="EWMA Trend (span=14)", mode="lines",
                line=dict(color="#22c55e", width=2.5, shape="spline"),
                hovertemplate="%{x|%b %d}<br>EWMA: %{y:,.0f}<extra></extra>"
            ))
        fig_area.update_layout(
            height=340,
            plot_bgcolor="rgba(30,32,40,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=40),
            legend=dict(
                orientation="h", yanchor="top", y=-0.12,
                xanchor="center", x=0.5,
                font=dict(color="rgba(255,255,255,0.7)", size=11),
                bgcolor="rgba(0,0,0,0)"
            ),
            hovermode="x unified"
        )
        fig_area.update_xaxes(
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            color="rgba(255,255,255,0.5)", zeroline=False,
            dtick="D1" if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and (date_range[1] - date_range[0]).days <= 45 else None,
            tickformat="%b %d" if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and (date_range[1] - date_range[0]).days <= 45 else None
        )
        fig_area.update_yaxes(
            showgrid=True, gridcolor="rgba(255,255,255,0.04)",
            color="rgba(255,255,255,0.5)", zeroline=False
        )
        st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})

        # ── Secondary chart: Volume bars by product ──────────────────────────
        # Use the same full date range as the top chart for consistent x-axis
        st.markdown('<div class="section-title">📊 Daily Shipment Volume by Product</div>',
                    unsafe_allow_html=True)

        bar_data = filtered.copy()
        # Reindex to full date range — every day gets a slot
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            _bar_dates = pd.date_range(date_range[0], date_range[1], freq="D")
        else:
            _bar_dates = pd.date_range(bar_data["Date"].min(), bar_data["Date"].max(), freq="D")

        color_map = {
            "55GAL Drum":   "#ff8c42",
            "1000L Tote":   "#22c55e",
            "330GAL Tote":  "#0052cc",
            "Other":        "#888888"
        }

        fig_bar = go.Figure()
        for item_type in ["55GAL Drum", "1000L Tote", "330GAL Tote", "Other"]:
            subset = bar_data[bar_data["Item Type"] == item_type]
            if subset.empty:
                continue
            daily = subset.groupby("Date")["Quantity"].sum()
            # Reindex to full date range, fill missing days with 0
            daily = daily.reindex(_bar_dates, fill_value=0)
            fig_bar.add_trace(go.Bar(
                x=daily.index, y=daily.values * surge_mult,
                name=item_type,
                marker_color=color_map.get(item_type, "#888"),
                hovertemplate="%{x|%b %d}<br>" + item_type + ": %{y:,.0f}<extra></extra>"
            ))

        fig_bar.update_layout(
            barmode="stack",
            height=280,
            plot_bgcolor="rgba(30,32,40,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=40),
            legend=dict(
                orientation="h", yanchor="top", y=-0.18,
                xanchor="center", x=0.5,
                font=dict(color="rgba(255,255,255,0.7)", size=11),
                bgcolor="rgba(0,0,0,0)"
            ),
            bargap=0.3
        )
        fig_bar.update_xaxes(
            showgrid=False, color="rgba(255,255,255,0.5)",
            tickformat="%b %d"
        )
        fig_bar.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.04)",
                             color="rgba(255,255,255,0.5)")
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    # ── Live Feed: Most recent 10 orders with amber highlighting ──────────
    with st.expander("📋 Live Order Feed — Most Recent Transactions", expanded=False):

        # Build the feed from sales + loop time join
        recent = filtered.nlargest(10, "Date").copy()
        recent["Customer"] = recent["Customer/Product"].str.split("(").str[0].str.strip()

        # Try to join with loop times to get transit data
        loop_map = dict(zip(
            df_loops["Customer Name"].str.strip(),
            df_loops["Total Transit Time (Days)"]
        ))
        recent["Loop Time (Days)"] = recent["Customer"].map(loop_map).fillna(0).astype(int)
        recent["Loop Time (Days)"] = (recent["Loop Time (Days)"] + logistics_delay).clip(lower=0)

        recent["Status"] = recent["Loop Time (Days)"].apply(
            lambda x: "🟡 Slow" if x > 30 else "🟢 Normal"
        )

        feed_df = recent[["Date", "Customer", "Item Type", "Quantity", "Loop Time (Days)", "Status"]].copy()
        feed_df["Date"] = feed_df["Date"].dt.strftime("%Y-%m-%d")
        feed_df["Quantity"] = (feed_df["Quantity"] * surge_mult).astype(int)

        # Style function for amber rows
        def _highlight_slow(row):
            if row.get("Status") == "🟡 Slow":
                return ["background-color: rgba(250, 204, 21, 0.10);"] * len(row)
            return [""] * len(row)

        styled_feed = feed_df.style.apply(_highlight_slow, axis=1)
        st.dataframe(styled_feed, use_container_width=True, hide_index=True, height=320)

    # ── Fleet Return Tracking & Compliance ───────────────────────────────
    st.markdown("""<hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:40px 0 20px;'>""",
                unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="font-size:1.5rem;">🔄 Fleet Return Tracking & EU Compliance</div>',
                unsafe_allow_html=True)
    st.caption("Live Twin Engine — Dynamic asset positioning & compliance-aware allocation (4.25-year EU limit)")

    fleet_df, alloc = get_fleet_status(df_sales, df_loops, df_mfg)

    # ── Row 1: Status cards ──────────────────────────────────────────────
    rt_c1, rt_c2, rt_c3, rt_c4 = st.columns(4)

    with rt_c1:
        _green_pct = alloc["fleet_green_pct"]
        _pct_color = "#22c55e" if _green_pct >= 40 else ("#facc15" if _green_pct >= 25 else "#ef4444")
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">🟢 GREEN FLEET</div>
            <div class="card-value" style="color:{_pct_color};">{_green_pct}%</div>
            <div class="card-delta delta-flat">{alloc["green_available"]} of {alloc["total_available"]} available</div>
            <div class="card-sub">EU-compliant (< 4.25 yrs)</div>
        </div>
        ''', unsafe_allow_html=True)

    with rt_c2:
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">📦 AT CUSTOMER</div>
            <div class="card-value" style="color:#38bdf8;">{alloc["at_customer"]}</div>
            <div class="card-delta delta-flat">{alloc["in_transit_out"]} in-transit out</div>
            <div class="card-sub">Assets currently deployed</div>
        </div>
        ''', unsafe_allow_html=True)

    with rt_c3:
        st.markdown(f'''
        <div class="sim-card">
            <div class="card-label">✅ AVAILABLE</div>
            <div class="card-value" style="color:#22c55e;">{alloc["available"]}</div>
            <div class="card-delta delta-flat">{alloc["in_transit_back"]} returning</div>
            <div class="card-sub">Ready for next allocation</div>
        </div>
        ''', unsafe_allow_html=True)

    with rt_c4:
        _stockout_color = "#ef4444" if alloc["compliance_stockout"] else "#22c55e"
        _stockout_label = "⚠️ STOCKOUT" if alloc["compliance_stockout"] else "✅ OK"
        st.markdown(f'''
        <div class="sim-card" style="border-color:{_stockout_color}40;">
            <div class="card-label">🌐 INTL COMPLIANCE</div>
            <div class="card-value" style="color:{_stockout_color};">{_stockout_label}</div>
            <div class="card-delta delta-flat">{alloc["intl_filled"]}/{alloc["intl_demand"]} filled</div>
            <div class="card-sub">20% intl demand coverage</div>
        </div>
        ''', unsafe_allow_html=True)

    # ── Row 2: Sankey Asset Lifecycle Flow + Allocation breakdown ────────
    st.markdown('<div class="section-title" style="font-size:1.15rem;margin-top:20px;">'
                '🌊 Asset Lifecycle Flow — Sankey Diagram</div>',
                unsafe_allow_html=True)

    # ── Synced from top-level filters (no separate dropdowns) ─────────────
    _mfg_customers = sorted(fleet_df["Customer"].unique().tolist())
    _sales_custs_raw = df_sales["Customer/Product"].str.split("(").str[0].str.strip()

    # Read from the top Command Center filters
    _sk_product_sel = sel_product    # "All" or e.g. "330GAL Tote"
    _sankey_selection = sel_customer  # "All" or e.g. "Customer AD-10"

    # Show active filter badge so user knows what's driving the Sankey
    _prod_display = _sk_product_sel if _sk_product_sel != "All" else "All Products"
    _cust_display = _sankey_selection if _sankey_selection != "All" else "All Customers"
    st.markdown(f'''
<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
  <span style="font-size:0.75rem;color:rgba(255,255,255,0.4);">Synced with filters above ▸</span>
  <span style="background:rgba(56,189,248,0.12);color:#38bdf8;padding:3px 10px;
              border-radius:8px;font-size:0.75rem;font-weight:600;">📦 {_prod_display}</span>
  <span style="background:rgba(167,139,250,0.12);color:#a78bfa;padding:3px 10px;
              border-radius:8px;font-size:0.75rem;font-weight:600;">👤 {_cust_display}</span>
</div>
    ''', unsafe_allow_html=True)

    # Filter sales data by selected product type
    if _sk_product_sel == "All":
        _sk_sales_filtered = df_sales
        _sk_custs_raw_filtered = _sales_custs_raw
    else:
        _product_mask = df_sales["Item Type"] == _sk_product_sel
        _sk_sales_filtered = df_sales[_product_mask]
        _sk_custs_raw_filtered = _sales_custs_raw[_product_mask]

    # ── Determine selection type and build Sankey data ─────────────────────
    _is_all = (_sankey_selection == "All")
    _is_mfg = _sankey_selection in _mfg_customers
    _is_sales = not _is_all and not _is_mfg

    if _is_all:
        # Fleet-wide: use all fleet_df data
        _sk_df = fleet_df
        _sk_label = "Fleet-Wide"
    elif _is_mfg:
        # MFG asset owner: filter fleet_df directly (serialized assets)
        _sk_df = fleet_df[fleet_df["Customer"] == _sankey_selection]
        _sk_label = _sankey_selection
    else:
        _sk_df = None  # Sales customer — different logic below
        _sk_label = _sankey_selection

    if _sk_df is not None:
        # ── MFG / Fleet-wide path: use actual serialized asset data ───────
        _sk_transit_out_green  = int(((_sk_df["Loop_Code"] == "in_transit_out") & _sk_df["Compliance"].str.contains("Green")).sum())
        _sk_transit_out_amber  = int(((_sk_df["Loop_Code"] == "in_transit_out") & _sk_df["Compliance"].str.contains("Amber")).sum())
        _sk_at_customer_green  = int(((_sk_df["Loop_Code"] == "at_customer") & _sk_df["Compliance"].str.contains("Green")).sum())
        _sk_at_customer_amber  = int(((_sk_df["Loop_Code"] == "at_customer") & _sk_df["Compliance"].str.contains("Amber")).sum())
        _sk_transit_back_green = int(((_sk_df["Loop_Code"] == "in_transit_back") & _sk_df["Compliance"].str.contains("Green")).sum())
        _sk_transit_back_amber = int(((_sk_df["Loop_Code"] == "in_transit_back") & _sk_df["Compliance"].str.contains("Amber")).sum())
        _sk_avail_green        = int(((_sk_df["Loop_Code"] == "available") & _sk_df["Compliance"].str.contains("Green")).sum())
        _sk_avail_amber        = int(((_sk_df["Loop_Code"] == "available") & _sk_df["Compliance"].str.contains("Amber")).sum())
        _sk_total              = len(_sk_df)
    else:
        # ── Sales customer path: derive flow from shipment activity ───────
        # Match this customer's sales + loop time data to estimate asset positions
        _sc_sales = _sk_sales_filtered[_sk_custs_raw_filtered == _sankey_selection].copy()
        _sc_sales["Date"] = pd.to_datetime(_sc_sales["Date"], errors="coerce")
        _sc_sales["Days_Ago"] = (pd.Timestamp.now() - _sc_sales["Date"]).dt.days

        # Find transit times from loop data (matching on cleaned name)
        _loop_custs_clean = df_loops["Customer Name"].str.split("(").str[0].str.strip()
        _sc_loop_match = df_loops[_loop_custs_clean == _sankey_selection]
        if _sc_loop_match.empty:
            # Fallback: try prefix match
            _sc_loop_match = df_loops[_loop_custs_clean.str.startswith(_sankey_selection.split()[0] + " " + _sankey_selection.split()[1] if len(_sankey_selection.split()) > 1 else _sankey_selection.split()[0])]

        if not _sc_loop_match.empty:
            _t_out  = int(_sc_loop_match.iloc[0].get("Transit Time to Customer Site (Days)", 7))
            _t_back = int(_sc_loop_match.iloc[0].get("Transit Time to MLI (Days)", 7))
            _t_dwell = int(_sc_loop_match.iloc[0].get("DOI Max at CS Site", 30))
            _t_total = int(_sc_loop_match.iloc[0].get("Total Transit Time (Days)", 60))
        else:
            _t_out, _t_back, _t_dwell, _t_total = 7, 7, 30, 60

        # Count quantities shipped in each time window (same logic as return_tracker.py)
        _q_transit_out  = int(_sc_sales[_sc_sales["Days_Ago"].between(0, _t_out)]["Quantity"].sum())
        _q_at_customer  = int(_sc_sales[_sc_sales["Days_Ago"].between(_t_out + 1, _t_out + _t_dwell)]["Quantity"].sum())
        _q_transit_back = int(_sc_sales[_sc_sales["Days_Ago"].between(_t_out + _t_dwell + 1, _t_total)]["Quantity"].sum())
        _q_total_flow   = _q_transit_out + _q_at_customer + _q_transit_back
        # Estimate available = total historical volume minus active in loop
        _q_total_hist   = int(_sc_sales["Quantity"].sum())
        _q_available    = max(0, _q_total_hist - _q_total_flow)
        _sk_total       = _q_total_flow + _q_available

        # For sales customers, estimate Green/Amber split from fleet-wide ratio
        _fleet_green_ratio = alloc["green_total"] / max(alloc["total_fleet"], 1)
        _fleet_amber_ratio = 1 - _fleet_green_ratio

        _sk_transit_out_green  = int(_q_transit_out * _fleet_green_ratio)
        _sk_transit_out_amber  = _q_transit_out - _sk_transit_out_green
        _sk_at_customer_green  = int(_q_at_customer * _fleet_green_ratio)
        _sk_at_customer_amber  = _q_at_customer - _sk_at_customer_green
        _sk_transit_back_green = int(_q_transit_back * _fleet_green_ratio)
        _sk_transit_back_amber = _q_transit_back - _sk_transit_back_green
        _sk_avail_green        = int(_q_available * _fleet_green_ratio)
        _sk_avail_amber        = _q_available - _sk_avail_green

    # ── Build Sankey figure ───────────────────────────────────────────────
    # Nodes: 0=Fleet Pool, 1=Green, 2=Amber, 3=Transit Out, 4=At Customer,
    #        5=Transit Back, 6=Available, 7=International, 8=Domestic
    _sk_labels = [
        f"Fleet Pool ({_sk_total:,})",
        f"🟢 Green ({_sk_transit_out_green + _sk_at_customer_green + _sk_transit_back_green + _sk_avail_green:,})",
        f"🟡 Amber ({_sk_transit_out_amber + _sk_at_customer_amber + _sk_transit_back_amber + _sk_avail_amber:,})",
        f"🚛 Transit Out ({_sk_transit_out_green + _sk_transit_out_amber:,})",
        f"📦 At Customer ({_sk_at_customer_green + _sk_at_customer_amber:,})",
        f"🔄 Transit Back ({_sk_transit_back_green + _sk_transit_back_amber:,})",
        f"✅ Available ({_sk_avail_green + _sk_avail_amber:,})",
        "🌍 International (EU)",
        "🏠 Domestic",
    ]
    _sk_node_colors = [
        "#0052cc", "#22c55e", "#facc15", "#ff8c42",
        "#38bdf8", "#a78bfa", "#22c55e", "#38bdf8", "#22c55e",
    ]

    _sk_source = [0, 0,   1, 1, 1, 1,   2, 2, 2, 2,   6, 6]
    _sk_target = [1, 2,   3, 4, 5, 6,   3, 4, 5, 6,   7, 8]
    _sk_values = [
        _sk_transit_out_green + _sk_at_customer_green + _sk_transit_back_green + _sk_avail_green,
        _sk_transit_out_amber + _sk_at_customer_amber + _sk_transit_back_amber + _sk_avail_amber,
        _sk_transit_out_green, _sk_at_customer_green, _sk_transit_back_green, _sk_avail_green,
        _sk_transit_out_amber, _sk_at_customer_amber, _sk_transit_back_amber, _sk_avail_amber,
        _sk_avail_green, _sk_avail_amber,
    ]
    _sk_link_colors = [
        "rgba(34, 197, 94, 0.35)", "rgba(250, 204, 21, 0.30)",
        "rgba(34, 197, 94, 0.25)", "rgba(34, 197, 94, 0.25)",
        "rgba(34, 197, 94, 0.25)", "rgba(34, 197, 94, 0.30)",
        "rgba(250, 204, 21, 0.20)", "rgba(250, 204, 21, 0.20)",
        "rgba(250, 204, 21, 0.20)", "rgba(250, 204, 21, 0.25)",
        "rgba(56, 189, 248, 0.35)", "rgba(34, 197, 94, 0.30)",
    ]

    # Remove zero-value links
    _sk_filtered = [(s, t, v, c) for s, t, v, c in
                    zip(_sk_source, _sk_target, _sk_values, _sk_link_colors) if v > 0]
    if _sk_filtered:
        _sk_source_f, _sk_target_f, _sk_values_f, _sk_colors_f = zip(*_sk_filtered)
    else:
        _sk_source_f, _sk_target_f, _sk_values_f, _sk_colors_f = [], [], [], []

    fig_sankey = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=22, thickness=28,
            line=dict(color="rgba(255,255,255,0.15)", width=1),
            label=list(_sk_labels),
            color=_sk_node_colors,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=list(_sk_source_f),
            target=list(_sk_target_f),
            value=list(_sk_values_f),
            color=list(_sk_colors_f),
            hovertemplate="<b>%{source.label}</b> → <b>%{target.label}</b>"
                          "<br>Units: %{value:,}<extra></extra>",
        ),
    ))
    fig_sankey.update_layout(
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white", size=11),
        margin=dict(l=10, r=10, t=10, b=10),
    )

    _sk_type_badge = ("📦 Asset Owner" if _is_mfg else
                      "👤 Sales Customer" if _is_sales else "🌍 Fleet")
    _sk_product_badge = f" · <b style='color:#ffaa00;'>{_sk_product_sel}</b>" if _sk_product_sel != "All" else ""
    st.markdown(f'<div style="font-size:0.85rem;color:rgba(255,255,255,0.5);'
                f'margin-bottom:4px;">{_sk_type_badge} · Showing: '
                f'<b style="color:white;">{_sk_label}</b>'
                f'{_sk_product_badge}'
                f' — {_sk_total:,} units</div>', unsafe_allow_html=True)

    st.plotly_chart(fig_sankey, use_container_width=True, config={"displayModeBar": False})

    # ── Optimal Fleet Size Suggestion ─────────────────────────────────────
    if sel_customer != "All":
        # Calculate daily demand from filtered sales
        _opt_sales = filtered.copy()
        _opt_sales["Date"] = pd.to_datetime(_opt_sales["Date"], errors="coerce")
        _opt_date_range = (_opt_sales["Date"].max() - _opt_sales["Date"].min()).days
        _opt_total_qty = _opt_sales["Quantity"].sum()
        _opt_daily = _opt_total_qty / max(_opt_date_range, 1)

        # Get loop time for this customer
        _opt_loop_names = df_loops["Customer Name"].str.split("(").str[0].str.strip()
        _opt_match = df_loops[_opt_loop_names == sel_customer]
        if _opt_match.empty:
            _opt_loop_time = df_loops["Total Transit Time (Days)"].mean()
            _opt_loop_src = "fleet avg"
        else:
            _opt_loop_time = _opt_match["Total Transit Time (Days)"].iloc[0]
            _opt_loop_src = "documented"

        # Optimal = daily_demand × loop_time × safety_buffer
        _safety = 1.20  # 20% buffer
        _opt_raw = _opt_daily * _opt_loop_time
        _opt_size = max(1, int(round(_opt_raw * _safety)))
        _opt_current = _sk_total

        # Delta
        _opt_delta = _opt_current - _opt_size
        if _opt_delta >= 0:
            _delta_color = "#22c55e"
            _delta_label = f"✅ Surplus of {_opt_delta}"
            _delta_icon = "🟢"
        else:
            _delta_color = "#ef4444"
            _delta_label = f"⚠️ Deficit of {abs(_opt_delta)}"
            _delta_icon = "🔴"

        # Product label
        _opt_prod = _sk_product_sel if _sk_product_sel != "All" else "all products"

        # One-line summary for the explanation
        _expl_summary = (
            f"{sel_customer}: "
            f"<b style='color:#facc15;'>{_opt_daily:.2f} units/day</b> × "
            f"<b style='color:#38bdf8;'>{_opt_loop_time:.0f}d</b> loop × "
            f"<b style='color:#a78bfa;'>1.2×</b> safety = "
            f"<b style='color:#22c55e;'>{_opt_size}</b> optimal"
        )

        st.markdown(f'''
<div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
            border-radius:14px;padding:20px 24px;margin-top:16px;margin-bottom:16px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;">
    <div>
      <div style="font-size:1.05rem;font-weight:800;color:white;display:flex;align-items:center;gap:8px;">
        🎯 Optimal Fleet Size Recommendation
      </div>
      <div style="font-size:0.75rem;color:rgba(255,255,255,0.35);margin-top:2px;">
        Based on demand velocity × loop time × 1.2× safety buffer
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);text-transform:uppercase;
                  letter-spacing:0.5px;">Current vs Optimal</div>
      <div style="font-size:0.8rem;font-weight:700;color:{_delta_color};margin-top:2px;">
        {_delta_icon} {_delta_label}
      </div>
    </div>
  </div>

  <div style="display:flex;gap:16px;margin-bottom:12px;">
    <div style="flex:1;background:rgba(255,255,255,0.04);border-radius:10px;
                padding:14px 16px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
      <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;
                  letter-spacing:0.5px;">Current Fleet</div>
      <div style="font-size:2rem;font-weight:800;color:white;margin:4px 0;">{_opt_current}</div>
      <div style="font-size:0.72rem;color:rgba(255,255,255,0.4);">containers</div>
    </div>
    <div style="flex:0 0 40px;display:flex;align-items:center;justify-content:center;
                font-size:1.3rem;color:rgba(255,255,255,0.25);">→</div>
    <div style="flex:1;background:rgba(34,197,94,0.08);border-radius:10px;
                padding:14px 16px;text-align:center;border:1px solid rgba(34,197,94,0.2);">
      <div style="font-size:0.65rem;color:rgba(34,197,94,0.7);text-transform:uppercase;
                  letter-spacing:0.5px;">Optimal Fleet</div>
      <div style="font-size:2rem;font-weight:800;color:#22c55e;margin:4px 0;">{_opt_size}</div>
      <div style="font-size:0.72rem;color:rgba(34,197,94,0.6);">recommended</div>
    </div>
    <div style="flex:0 0 40px;display:flex;align-items:center;justify-content:center;
                font-size:1.3rem;color:rgba(255,255,255,0.25);">→</div>
    <div style="flex:1;background:rgba(250,204,21,0.06);border-radius:10px;
                padding:14px 16px;text-align:center;border:1px solid rgba(250,204,21,0.15);">
      <div style="font-size:0.65rem;color:rgba(250,204,21,0.7);text-transform:uppercase;
                  letter-spacing:0.5px;">Delta</div>
      <div style="font-size:2rem;font-weight:800;color:{_delta_color};margin:4px 0;">
        {'+' if _opt_delta >= 0 else ''}{_opt_delta}</div>
      <div style="font-size:0.72rem;color:rgba(255,255,255,0.4);">
        {'surplus' if _opt_delta >= 0 else 'shortage'}</div>
    </div>
  </div>

  <div style="font-size:0.75rem;color:rgba(255,255,255,0.5);line-height:1.5;">
    {_expl_summary}
  </div>
</div>
        ''', unsafe_allow_html=True)


    # ── Row 3: Allocation breakdown ──────────────────────────────────────
    rt_left, rt_right = st.columns(2)

    with rt_left:
        st.markdown('<div class="section-title">📋 20/80 Allocation Breakdown</div>',
                    unsafe_allow_html=True)

        # International allocation
        _intl_fill_pct = round(100 * alloc["intl_filled"] / max(alloc["intl_demand"], 1))
        st.markdown(f'''
        <div style="padding:12px 16px;background:rgba(30,32,40,0.5);border-radius:12px;
                    border-left:4px solid #38bdf8;margin-bottom:12px;">
            <div style="font-size:0.85rem;color:#38bdf8;font-weight:600;">🌐 International / EU (20%)</div>
            <div style="display:flex;align-items:center;gap:12px;margin-top:8px;">
                <div style="font-size:1.8rem;font-weight:700;color:white;">{alloc["intl_filled"]}</div>
                <div style="flex:1;">
                    <div style="background:rgba(255,255,255,0.1);border-radius:6px;height:12px;overflow:hidden;">
                        <div style="background:#38bdf8;width:{_intl_fill_pct}%;height:100%;border-radius:6px;transition:width 0.5s;"></div>
                    </div>
                    <div style="font-size:0.75rem;color:rgba(255,255,255,0.5);margin-top:4px;">
                        {alloc["intl_filled"]} of {alloc["intl_demand"]} demand · Green assets only
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # Domestic allocation
        _dom_fill_pct = round(100 * alloc["domestic_filled"] / max(alloc["domestic_demand"], 1))
        st.markdown(f'''
        <div style="padding:12px 16px;background:rgba(30,32,40,0.5);border-radius:12px;
                    border-left:4px solid #22c55e;margin-bottom:12px;">
            <div style="font-size:0.85rem;color:#22c55e;font-weight:600;">🏠 Domestic (80%)</div>
            <div style="display:flex;align-items:center;gap:12px;margin-top:8px;">
                <div style="font-size:1.8rem;font-weight:700;color:white;">{alloc["domestic_filled"]}</div>
                <div style="flex:1;">
                    <div style="background:rgba(255,255,255,0.1);border-radius:6px;height:12px;overflow:hidden;">
                        <div style="background:#22c55e;width:{_dom_fill_pct}%;height:100%;border-radius:6px;transition:width 0.5s;"></div>
                    </div>
                    <div style="font-size:0.75rem;color:rgba(255,255,255,0.5);margin-top:4px;">
                        {alloc["domestic_filled"]} of {alloc["domestic_demand"]} demand · Green + Amber
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    with rt_right:
        st.markdown('<div class="section-title">⏰ Asset Expiry & Risk</div>',
                    unsafe_allow_html=True)

        # Expiry watch
        _exp_color = "#ef4444" if alloc["assets_expiring_30d"] > 0 else "#facc15"
        st.markdown(f'''
        <div style="padding:12px 16px;background:rgba(30,32,40,0.5);border-radius:12px;
                    border-left:4px solid {_exp_color};margin-bottom:12px;">
            <div style="font-size:0.85rem;color:{_exp_color};font-weight:600;">⏰ Expiry Watch</div>
            <div style="display:flex;gap:24px;margin-top:6px;">
                <div>
                    <span style="font-size:1.3rem;font-weight:700;color:white;">{alloc["assets_expiring_30d"]}</span>
                    <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);"> in 30 days</span>
                </div>
                <div>
                    <span style="font-size:1.3rem;font-weight:700;color:white;">{alloc["assets_expiring_90d"]}</span>
                    <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);"> in 90 days</span>
                </div>
                <div>
                    <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">Next expiry: </span>
                    <span style="font-size:1rem;font-weight:600;color:{_exp_color};">{alloc["next_expiry_days"]}d</span>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # Customer-specific Sankey insight card (only when a customer is selected)
        if not _is_all:
            _sk_cust_total   = _sk_total
            _sk_cust_in_loop = (_sk_transit_out_green + _sk_transit_out_amber +
                                _sk_at_customer_green + _sk_at_customer_amber +
                                _sk_transit_back_green + _sk_transit_back_amber)
            _sk_cust_avail   = _sk_avail_green + _sk_avail_amber
            _sk_util_pct     = round(100 * _sk_cust_in_loop / max(_sk_cust_total, 1), 1)
            _sk_green_pct    = round(100 * (_sk_transit_out_green + _sk_at_customer_green +
                                            _sk_transit_back_green + _sk_avail_green) /
                                     max(_sk_cust_total, 1), 1)
            _util_color = "#22c55e" if _sk_util_pct < 70 else ("#facc15" if _sk_util_pct < 90 else "#ef4444")
            st.markdown(f'''
            <div style="padding:14px 16px;background:rgba(30,32,40,0.5);border-radius:12px;
                        border-left:4px solid #0052cc;">
                <div style="font-size:0.85rem;color:#0052cc;font-weight:600;">
                    📊 {_sankey_selection} — Asset Profile
                </div>
                <div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap;">
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:700;color:white;">{_sk_cust_total}</div>
                        <div style="font-size:0.7rem;color:rgba(255,255,255,0.5);">Total Assets</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:700;color:{_util_color};">{_sk_util_pct}%</div>
                        <div style="font-size:0.7rem;color:rgba(255,255,255,0.5);">In-Loop Utilization</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:700;color:#22c55e;">{_sk_green_pct}%</div>
                        <div style="font-size:0.7rem;color:rgba(255,255,255,0.5);">EU-Compliant</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:700;color:#22c55e;">{_sk_cust_avail}</div>
                        <div style="font-size:0.7rem;color:rgba(255,255,255,0.5);">Available Now</div>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

    # ── Age Compliance Histogram ─────────────────────────────────────────
    with st.expander("📊 Fleet Age Distribution", expanded=False):
        fig_age = go.Figure()
        green_ages = fleet_df[fleet_df["Compliance"].str.contains("Green")]["Age_Days"]
        amber_ages = fleet_df[fleet_df["Compliance"].str.contains("Amber")]["Age_Days"]

        fig_age.add_trace(go.Histogram(
            x=green_ages, name="🟢 Green (EU-OK)",
            marker_color="rgba(34, 197, 94, 0.6)",
            marker_line=dict(color="rgba(255,255,255,0.15)", width=1),
            nbinsx=30
        ))
        fig_age.add_trace(go.Histogram(
            x=amber_ages, name="🟡 Amber (Domestic)",
            marker_color="rgba(250, 204, 21, 0.5)",
            marker_line=dict(color="rgba(255,255,255,0.15)", width=1),
            nbinsx=30
        ))
        fig_age.add_vline(
            x=1551, line_dash="dash", line_color="#ef4444", line_width=2,
            annotation_text="EU Limit (4.25 yrs)",
            annotation_font_color="#ef4444",
            annotation_font_size=12
        )
        fig_age.update_layout(
            barmode="overlay",
            height=280,
            plot_bgcolor="rgba(30,32,40,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=40),
            xaxis_title="Asset Age (Days)",
            yaxis_title="Count",
            legend=dict(
                orientation="h", yanchor="top", y=-0.15,
                xanchor="center", x=0.5,
                font=dict(color="rgba(255,255,255,0.7)", size=11)
            ),
        )
        fig_age.update_xaxes(color="rgba(255,255,255,0.5)")
        fig_age.update_yaxes(color="rgba(255,255,255,0.5)")
        st.plotly_chart(fig_age, use_container_width=True, config={"displayModeBar": False})



