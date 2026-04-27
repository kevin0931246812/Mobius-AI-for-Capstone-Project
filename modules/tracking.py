"""
pages/tracking.py
-----------------
Tracking Return Status — Serial-level asset tracking dashboard.

Renders:
  - Filter bar (serial search, status, compliance, product, customer)
  - KPI cards (total assets, transit out/back, dwelling, available, green fleet)
  - Serial Number Registry table
  - Serial Detail Inspector with 4-stage pipeline visualization
  - Status Distribution donut + Age Distribution histogram
  - CSV export
"""
from __future__ import annotations

import os
import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mfg_generator import sync_mfg_data
from return_tracker import update_return_tracking

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render():
    """Render the Tracking Return Status page."""
    st.markdown('''
    <style>
    .trk-kpi {
        background: rgba(30, 32, 40, 0.55);
        backdrop-filter: blur(18px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 18px 20px;
        text-align: center;
    }
    .trk-kpi .kpi-label {
        font-size: 0.75rem; color: rgba(255,255,255,0.5);
        text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
    }
    .trk-kpi .kpi-value {
        font-size: 2.2rem; font-weight: 800; margin: 4px 0 2px;
    }
    .trk-kpi .kpi-sub {
        font-size: 0.8rem; color: rgba(255,255,255,0.4);
    }
    .serial-card {
        background: rgba(30,32,40,0.5);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 12px;
    }
    </style>
    ''', unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown('''
    <div style="margin-bottom:28px;">
        <h1 style="font-size:2.4rem;font-weight:800;margin:0 0 4px;
                   background:linear-gradient(135deg,#ffffff 0%,#a0aec0 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            📦 Tracking Return Status
        </h1>
        <p style="color:#8892b0;font-size:1rem;margin:0;">
            Serial-level asset tracking — Monitor every returnable container across the supply chain loop
        </p>
    </div>
    ''', unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────
    @st.cache_data(show_spinner=False)
    def _load_tracking_data(_ts: float):
        sales = pd.read_csv(os.path.join(_BASE, "FINAL_Sales_QTY.csv"), parse_dates=["Date"])
        loops = pd.read_csv(os.path.join(_BASE, "FINAL_Documented_Loop_Times.csv"))
        r2r   = pd.read_csv(os.path.join(_BASE, "FINAL_Receipt_to_Receipt_Data.csv"))
        mfg = sync_mfg_data(
            sales_path=os.path.join(_BASE, "FINAL_Sales_QTY.csv"),
            mfg_path=os.path.join(_BASE, "FINAL_MFG_Date.csv"),
        )
        fleet = update_return_tracking(sales, loops, mfg)
        return fleet

    try:
        _trk_mtime = os.path.getmtime(os.path.join(_BASE, "FINAL_Sales_QTY.csv"))
    except FileNotFoundError:
        _trk_mtime = 0

    try:
        fleet_trk = _load_tracking_data(_trk_mtime)
    except Exception as e:
        st.error(f"⚠️ **Data loading failed.** Please ensure all FINAL_ CSV files exist in the project directory.\\n\\n`{e}`")
        st.stop()

    # ── Classify product type from Item column ────────────────────────────
    def _trk_product(item_str):
        u = str(item_str).upper()
        if "1000L" in u: return "1000L Tote"
        if "55GAL" in u or "DR-55GAL" in u: return "55GAL Drum"
        if "330GAL" in u or "TT-330GAL" in u: return "330GAL Tote"
        return "Other"

    fleet_trk["Product_Type"] = fleet_trk["Item"].apply(_trk_product)

    # ── Filters ───────────────────────────────────────────────────────────
    st.markdown('<div style="margin-bottom:8px;font-size:0.85rem;color:rgba(255,255,255,0.5);'
                'font-weight:600;letter-spacing:1px;">🔍 FILTER ASSETS</div>',
                unsafe_allow_html=True)

    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])

    with fc1:
        serial_search = st.text_input("🔎 Search Serial Number", placeholder="MLI-DR-7001...", key="trk_search")

    with fc2:
        status_filter = st.selectbox("📍 Status", ["All"] + sorted(fleet_trk["Loop_Status"].unique().tolist()), key="trk_status")

    with fc3:
        compliance_filter = st.selectbox("🏷️ Compliance", ["All", "🟢 Green", "🟡 Amber"], key="trk_compliance")

    with fc4:
        product_filter = st.selectbox("📦 Product", ["All"] + sorted(fleet_trk["Product_Type"].unique().tolist()), key="trk_product")

    with fc5:
        customer_filter = st.selectbox("👤 Customer", ["All"] + sorted(fleet_trk["Customer"].unique().tolist()), key="trk_customer")

    # ── Apply filters ─────────────────────────────────────────────────────
    df_display = fleet_trk.copy()

    if serial_search:
        df_display = df_display[df_display["Serial"].str.contains(serial_search, case=False, na=False)]
    if status_filter != "All":
        df_display = df_display[df_display["Loop_Status"] == status_filter]
    if compliance_filter != "All":
        df_display = df_display[df_display["Compliance"] == compliance_filter]
    if product_filter != "All":
        df_display = df_display[df_display["Product_Type"] == product_filter]
    if customer_filter != "All":
        df_display = df_display[df_display["Customer"] == customer_filter]

    # ── KPI Cards ─────────────────────────────────────────────────────────
    _total_assets = len(df_display)
    _in_transit_out = int((df_display["Loop_Code"] == "in_transit_out").sum())
    _at_customer = int((df_display["Loop_Code"] == "at_customer").sum())
    _in_transit_back = int((df_display["Loop_Code"] == "in_transit_back").sum())
    _available = int((df_display["Loop_Code"] == "available").sum())
    _green = int(df_display["Compliance"].str.contains("Green").sum())
    _amber = _total_assets - _green
    _green_pct = round(100 * _green / max(_total_assets, 1), 1)
    _avg_age = round(df_display["Age_Days"].mean()) if _total_assets > 0 else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">Total Assets</div>
            <div class="kpi-value" style="color:#38bdf8;">{_total_assets:,}</div>
            <div class="kpi-sub">Matching filters</div>
        </div>''', unsafe_allow_html=True)

    with k2:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">🚛 Transit Out</div>
            <div class="kpi-value" style="color:#ff8c42;">{_in_transit_out:,}</div>
            <div class="kpi-sub">To customer</div>
        </div>''', unsafe_allow_html=True)

    with k3:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">📦 At Customer</div>
            <div class="kpi-value" style="color:#facc15;">{_at_customer:,}</div>
            <div class="kpi-sub">Dwelling</div>
        </div>''', unsafe_allow_html=True)

    with k4:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">🔄 Transit Back</div>
            <div class="kpi-value" style="color:#a78bfa;">{_in_transit_back:,}</div>
            <div class="kpi-sub">Returning to MLI</div>
        </div>''', unsafe_allow_html=True)

    with k5:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">✅ Available</div>
            <div class="kpi-value" style="color:#22c55e;">{_available:,}</div>
            <div class="kpi-sub">Ready to ship</div>
        </div>''', unsafe_allow_html=True)

    with k6:
        st.markdown(f'''
        <div class="trk-kpi">
            <div class="kpi-label">🟢 Green Fleet</div>
            <div class="kpi-value" style="color:#22c55e;">{_green_pct}%</div>
            <div class="kpi-sub">{_green:,} Green · {_amber:,} Amber</div>
        </div>''', unsafe_allow_html=True)

    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    # ── Asset Tracking Table ──────────────────────────────────────────────
    st.markdown(f'''
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div class="section-title" style="margin:0;">📋 Serial Number Registry — {_total_assets:,} assets</div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.4);">
            Avg Age: {_avg_age:,} days · Green/Amber: {_green}/{_amber}
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Build display dataframe
    df_table = df_display[["Serial", "Customer", "Product_Type", "Compliance",
                           "Loop_Status", "Age_Days", "MFG_Date", "Transit_Total"]].copy()
    df_table.columns = ["Serial #", "Customer", "Product", "Compliance",
                        "Status", "Age (Days)", "MFG Date", "Loop Time"]
    df_table["MFG Date"] = pd.to_datetime(df_table["MFG Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df_table["Days Until Amber"] = df_table["Age (Days)"].apply(
        lambda x: max(0, 1551 - x) if x <= 1551 else 0
    )
    df_table = df_table.sort_values("Serial #").reset_index(drop=True)

    # Show the table (read-only display)
    st.dataframe(
        df_table,
        use_container_width=True,
        height=500,
        column_config={
            "Serial #": st.column_config.TextColumn("Serial #", width="medium"),
            "Customer": st.column_config.TextColumn("Customer", width="medium"),
            "Product": st.column_config.TextColumn("Product", width="small"),
            "Compliance": st.column_config.TextColumn("Compliance", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
            "Age (Days)": st.column_config.NumberColumn("Age (Days)", format="%d"),
            "MFG Date": st.column_config.TextColumn("MFG Date", width="small"),
            "Loop Time": st.column_config.NumberColumn("Loop (d)", format="%d"),
            "Days Until Amber": st.column_config.ProgressColumn(
                "Days Until Amber",
                min_value=0,
                max_value=1551,
                format="%d days",
            ),
        },
    )

    # ── Serial Detail Inspector ───────────────────────────────────────────
    st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔬 Serial Detail Inspector</div>', unsafe_allow_html=True)
    st.caption("Select a serial number from the list or type to search.")

    _serial_options = [""] + sorted(df_table["Serial #"].tolist())
    _inspect_serial = st.selectbox(
        "Select Serial #",
        options=_serial_options,
        index=0,
        format_func=lambda x: "Type to search serials..." if x == "" else x,
        key="trk_inspect_serial",
    )

    if _inspect_serial:
        _match = fleet_trk[fleet_trk["Serial"].str.contains(_inspect_serial, case=False, na=False)]
        if _match.empty:
            st.warning(f"No asset found matching '{_inspect_serial}'")
        else:
            _asset = _match.iloc[0]
            _age = int(_asset["Age_Days"])
            _comp_color = "#22c55e" if "Green" in str(_asset["Compliance"]) else "#facc15"
            _status_icons = {
                "in_transit_out": ("🚛", "#ff8c42", "In-Transit to Customer"),
                "at_customer": ("📦", "#facc15", "At Customer Site"),
                "in_transit_back": ("🔄", "#a78bfa", "Returning to MLI"),
                "available": ("✅", "#22c55e", "Available at MLI"),
            }
            _s_icon, _s_color, _s_text = _status_icons.get(
                _asset["Loop_Code"], ("❓", "#888", "Unknown")
            )
            _days_until_amber = max(0, 1551 - _age) if _age <= 1551 else 0
            _mfg_str = pd.to_datetime(_asset["MFG_Date"], errors="coerce")
            _mfg_display = _mfg_str.strftime("%B %d, %Y") if pd.notna(_mfg_str) else "Unknown"
            _product_type = _trk_product(_asset["Item"])
            _amber_cd_color = "#22c55e" if _days_until_amber > 365 else ("#facc15" if _days_until_amber > 90 else "#ef4444")
            _eligible_text = "🌍 Intl + 🏠 Domestic" if "Green" in str(_asset["Compliance"]) else "🏠 Domestic Only"
            _age_yrs = round(_age / 365, 1)

            # New pipeline data
            _t_to_cust = int(_asset.get("Transit_To_Cust", 0))
            _t_dwell = int(_asset.get("Transit_Dwell", 0))
            _t_to_mli = int(_asset.get("Transit_To_MLI", 0))
            _t_total = int(_asset.get("Transit_Total", 0))
            _order_date = _asset.get("Order_Date", pd.NaT)
            _days_since = int(_asset.get("Days_Since_Order", 0))
            _days_return = int(_asset.get("Days_Until_Return", 0))

            _order_display = "—"
            _eta_cust_display = "—"
            _eta_leave_display = "—"
            _eta_mli_display = "—"
            if pd.notna(_order_date):
                _order_display = pd.to_datetime(_order_date).strftime("%b %d, %Y")
            _eta_cust = _asset.get("ETA_At_Customer", pd.NaT)
            _eta_leave = _asset.get("ETA_Leave_Customer", pd.NaT)
            _eta_mli = _asset.get("ETA_Return_MLI", pd.NaT)
            if pd.notna(_eta_cust):
                _eta_cust_display = pd.to_datetime(_eta_cust).strftime("%b %d, %Y")
            if pd.notna(_eta_leave):
                _eta_leave_display = pd.to_datetime(_eta_leave).strftime("%b %d, %Y")
            if pd.notna(_eta_mli):
                _eta_mli_display = pd.to_datetime(_eta_mli).strftime("%b %d, %Y")

            # Stage status for pipeline highlighting
            _code = str(_asset["Loop_Code"])
            _stages = [
                ("available", "🏭", "At MLI<br>Inventory", "#22c55e"),
                ("in_transit_out", "🚛", "Transit<br>→ Customer", "#ff8c42"),
                ("at_customer", "📦", "At Customer<br>Site", "#facc15"),
                ("in_transit_back", "🔄", "Returning<br>→ MLI", "#a78bfa"),
            ]

            # Map code to stage index
            _stage_map = {"available": 0, "in_transit_out": 1, "at_customer": 2, "in_transit_back": 3}
            _current_idx = _stage_map.get(_code, 0)

            # Build pipeline stages HTML
            _pipeline_stages = ""
            for idx, (code, icon, label, color) in enumerate(_stages):
                is_current = (idx == _current_idx)
                is_done = (idx < _current_idx) if _code != "available" else (idx == 0)

                if is_current:
                    bg = f"{color}33"
                    border = f"2px solid {color}"
                    opacity = "1"
                    glow = f"box-shadow: 0 0 20px {color}44;"
                    badge = f'<div style="position:absolute;top:-8px;right:-8px;background:{color};color:#0a0e17;font-size:0.6rem;font-weight:800;padding:2px 6px;border-radius:8px;">NOW</div>'
                elif is_done:
                    bg = "rgba(255,255,255,0.05)"
                    border = "1px solid rgba(255,255,255,0.15)"
                    opacity = "0.5"
                    glow = ""
                    badge = ""
                else:
                    bg = "rgba(255,255,255,0.03)"
                    border = "1px dashed rgba(255,255,255,0.1)"
                    opacity = "0.35"
                    glow = ""
                    badge = ""

                # Duration label for each stage
                if idx == 0:
                    dur_label = "Ready"
                elif idx == 1:
                    dur_label = f"{_t_to_cust}d"
                elif idx == 2:
                    dur_label = f"{_t_dwell}d"
                else:
                    dur_label = f"{_t_to_mli}d"

                _pipeline_stages += f'''
                <div style="position:relative;flex:1;text-align:center;padding:14px 6px;
                            background:{bg};border:{border};border-radius:12px;
                            opacity:{opacity};transition:all 0.3s;{glow}">
                    {badge}
                    <div style="font-size:1.5rem;margin-bottom:4px;">{icon}</div>
                    <div style="font-size:0.72rem;color:rgba(255,255,255,0.7);line-height:1.3;">{label}</div>
                    <div style="font-size:0.7rem;color:{color};font-weight:700;margin-top:4px;">{dur_label}</div>
                </div>'''

            # Build connector arrows between stages
            _arrow_html = ""
            for idx in range(3):
                done = (idx < _current_idx) if _code != "available" else False
                arr_color = "rgba(255,255,255,0.3)" if done else "rgba(255,255,255,0.1)"
                _arrow_html += f'''
                <div style="flex:0 0 24px;display:flex;align-items:center;justify-content:center;
                            font-size:1rem;color:{arr_color};">▸</div>'''

            # Interleave stages and arrows
            _interleaved = ""
            for idx in range(4):
                code_s = _stages[idx][0]
                is_curr = (idx == _current_idx)
                is_d = (idx < _current_idx) if _code != "available" else (idx == 0)
                icon_s = _stages[idx][1]
                label_s = _stages[idx][2]
                color_s = _stages[idx][3]

                if is_curr:
                    bg = f"{color_s}33"; border = f"2px solid {color_s}"; op = "1"
                    glow = f"box-shadow: 0 0 20px {color_s}44;"
                    badge = f'<div style="position:absolute;top:-8px;right:-8px;background:{color_s};color:#0a0e17;font-size:0.55rem;font-weight:800;padding:2px 6px;border-radius:8px;letter-spacing:0.5px;">NOW</div>'
                elif is_d:
                    bg = "rgba(255,255,255,0.05)"; border = "1px solid rgba(255,255,255,0.15)"; op = "0.5"
                    glow = ""; badge = ""
                else:
                    bg = "rgba(255,255,255,0.03)"; border = "1px dashed rgba(255,255,255,0.1)"; op = "0.35"
                    glow = ""; badge = ""

                if idx == 0: dur_l = "Ready"
                elif idx == 1: dur_l = f"{_t_to_cust} days"
                elif idx == 2: dur_l = f"{_t_dwell} days"
                else: dur_l = f"{_t_to_mli} days"

                _interleaved += f'''<div style="position:relative;flex:1;text-align:center;padding:14px 6px;
                    background:{bg};border:{border};border-radius:12px;
                    opacity:{op};transition:all 0.3s;{glow}">
                    {badge}
                    <div style="font-size:1.4rem;margin-bottom:4px;">{icon_s}</div>
                    <div style="font-size:0.7rem;color:rgba(255,255,255,0.7);line-height:1.3;">{label_s}</div>
                    <div style="font-size:0.65rem;color:{color_s};font-weight:700;margin-top:4px;">{dur_l}</div>
                </div>'''

                if idx < 3:
                    arr_c = "rgba(255,255,255,0.3)" if (idx < _current_idx and _code != "available") else "rgba(255,255,255,0.1)"
                    _interleaved += f'<div style="flex:0 0 20px;display:flex;align-items:center;justify-content:center;font-size:0.9rem;color:{arr_c};">▸</div>'

            # Order / return info row
            if _code == "available":
                _order_row = f'''
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:16px;
                            padding:14px 16px;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);
                            border-radius:10px;">
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Status</div>
                        <div style="font-size:0.95rem;font-weight:600;color:#22c55e;margin-top:3px;">In Inventory — Ready to Ship</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Full Loop Time</div>
                        <div style="font-size:0.95rem;font-weight:600;color:white;margin-top:3px;">{_t_total} days ({_t_to_cust}d + {_t_dwell}d + {_t_to_mli}d)</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Eligible For</div>
                        <div style="font-size:0.95rem;font-weight:600;color:white;margin-top:3px;">{_eligible_text}</div>
                    </div>
                </div>'''
            else:
                _progress_pct = min(100, round(100 * _days_since / max(_t_total, 1)))
                _order_row = f'''
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-top:16px;
                            padding:14px 16px;background:rgba(255,140,66,0.08);border:1px solid rgba(255,140,66,0.2);
                            border-radius:10px;">
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Order Date</div>
                        <div style="font-size:0.95rem;font-weight:600;color:white;margin-top:3px;">{_order_display}</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Days in Loop</div>
                        <div style="font-size:0.95rem;font-weight:600;color:#ff8c42;margin-top:3px;">{_days_since} / {_t_total} days</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">ETA Return to MLI</div>
                        <div style="font-size:0.95rem;font-weight:600;color:#a78bfa;margin-top:3px;">{_eta_mli_display}</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Days Until Return</div>
                        <div style="font-size:0.95rem;font-weight:600;color:#38bdf8;margin-top:3px;">{_days_return} days</div>
                    </div>
                </div>
                <div style="margin-top:8px;background:rgba(255,255,255,0.06);border-radius:6px;height:6px;overflow:hidden;">
                    <div style="width:{_progress_pct}%;height:100%;background:linear-gradient(90deg,#ff8c42,#a78bfa);border-radius:6px;transition:width 0.5s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:0.6rem;color:rgba(255,255,255,0.3);">
                    <span>Shipped {_order_display}</span>
                    <span>{_progress_pct}% complete</span>
                    <span>Return {_eta_mli_display}</span>
                </div>'''

            _card_html = f"""
            <div class="serial-card" style="border-left:4px solid {_s_color};">
                <div style="display:flex;justify-content:space-between;align-items:start;">
                    <div>
                        <div style="font-size:1.6rem;font-weight:800;color:white;letter-spacing:1px;">
                            {_asset["Serial"]}
                        </div>
                        <div style="font-size:0.85rem;color:rgba(255,255,255,0.5);margin-top:2px;">
                            {_asset["Item"]} · {_product_type}
                        </div>
                    </div>
                    <div style="background:{_s_color}22;border:1px solid {_s_color};
                                border-radius:8px;padding:6px 14px;font-size:0.85rem;
                                color:{_s_color};font-weight:600;">
                        {_s_icon} {_s_text}
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:14px;margin-top:16px;">
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Customer</div>
                        <div style="font-size:0.95rem;font-weight:600;color:white;margin-top:3px;">{_asset["Customer"]}</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">MFG Date</div>
                        <div style="font-size:0.95rem;font-weight:600;color:white;margin-top:3px;">{_mfg_display}</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Asset Age · Compliance</div>
                        <div style="font-size:0.95rem;font-weight:600;color:{_comp_color};margin-top:3px;">{_age:,}d ({_age_yrs}y) · {_asset["Compliance"]}</div>
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">Days Until Amber</div>
                        <div style="font-size:0.95rem;font-weight:600;color:{_amber_cd_color};margin-top:3px;">{_days_until_amber:,} days</div>
                    </div>
                </div>

                <!-- 4-Stage Pipeline -->
                <div style="margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.06);">
                    <div style="font-size:0.7rem;color:rgba(255,255,255,0.4);text-transform:uppercase;
                                letter-spacing:1px;font-weight:600;margin-bottom:12px;">
                        📍 Loop Journey Pipeline — {_t_total} Day Cycle
                    </div>
                    <div style="display:flex;align-items:stretch;gap:0;">
                        {_interleaved}
                    </div>
                </div>

                {_order_row}
            </div>
            """
            st.html(_card_html)

            # ── Shipped With — Co-shipped containers ──────────────────
            if pd.notna(_order_date):
                _od = pd.to_datetime(_order_date).normalize()
                _co_shipped = fleet_trk[
                    (fleet_trk["Customer"] == _asset["Customer"]) &
                    (pd.to_datetime(fleet_trk["Order_Date"], errors="coerce").dt.normalize() == _od) &
                    (fleet_trk["Serial"] != _asset["Serial"])
                ]
                if not _co_shipped.empty:
                    _co_shipped = _co_shipped.copy()
                    _co_shipped["Product_Type"] = _co_shipped["Item"].apply(_trk_product)
                    _co_by_product = _co_shipped.groupby("Product_Type")

                    _product_colors = {
                        "1000L Tote": "#38bdf8", "330GAL Tote": "#a78bfa",
                        "55GAL Drum": "#facc15", "Other": "#8892b0",
                    }

                    _shipped_rows = ""
                    for _p_type, _p_group in _co_by_product:
                        _p_color = _product_colors.get(_p_type, "#8892b0")
                        _serials_list = _p_group.sort_values("Serial")
                        _serial_badges = ""
                        _show_count = min(6, len(_serials_list))
                        for _, _sr in _serials_list.head(_show_count).iterrows():
                            _sr_comp = "🟢" if "Green" in str(_sr["Compliance"]) else "🟡"
                            _sr_icon = {"in_transit_out": "🚛", "at_customer": "📦",
                                        "in_transit_back": "🔄", "available": "✅"
                                        }.get(_sr["Loop_Code"], "❓")
                            _serial_badges += (
                                f'<span style="display:inline-flex;align-items:center;gap:3px;'
                                f'background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
                                f'border-radius:6px;padding:3px 8px;font-size:0.7rem;'
                                f'color:rgba(255,255,255,0.7);">'
                                f'{_sr_icon} {_sr_comp} {_sr["Serial"]}</span>')
                        if len(_serials_list) > _show_count:
                            _serial_badges += (
                                f'<span style="font-size:0.7rem;color:rgba(255,255,255,0.35);'
                                f'padding:3px 6px;">...+{len(_serials_list) - _show_count} more</span>')

                        _shipped_rows += (
                            f'<div style="margin-bottom:10px;">'
                            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
                            f'<span style="background:{_p_color}18;color:{_p_color};'
                            f'padding:2px 10px;border-radius:6px;font-size:0.72rem;'
                            f'font-weight:700;border:1px solid {_p_color}30;">{_p_type}</span>'
                            f'<span style="font-size:0.72rem;color:rgba(255,255,255,0.4);">'
                            f'{len(_serials_list)} container{"s" if len(_serials_list) != 1 else ""}'
                            f'</span></div>'
                            f'<div style="display:flex;flex-wrap:wrap;gap:4px;">'
                            f'{_serial_badges}</div></div>')

                    _od_display = pd.to_datetime(_order_date).strftime("%b %d, %Y")
                    st.markdown(
                        f'<div style="background:rgba(30,32,40,0.5);border:1px solid rgba(255,255,255,0.08);'
                        f'border-radius:14px;padding:16px 20px;margin-top:12px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
                        f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<span style="font-size:1rem;">📦</span>'
                        f'<span style="font-size:0.9rem;font-weight:700;color:white;">'
                        f'Shipped With — Same Order ({_od_display})</span></div>'
                        f'<span style="font-size:0.72rem;color:rgba(255,255,255,0.35);">'
                        f'{len(_co_shipped)} other container{"s" if len(_co_shipped) != 1 else ""} · '
                        f'{_asset["Customer"]}</span></div>'
                        f'{_shipped_rows}'
                        f'<div style="margin-top:8px;font-size:0.65rem;color:rgba(255,255,255,0.25);">'
                        f'🟢 Green (EU eligible) · 🟡 Amber (domestic only) · '
                        f'🚛 Transit → 📦 Customer → 🔄 Returning → ✅ Available</div></div>',
                        unsafe_allow_html=True)

    # ── Status Distribution Chart ─────────────────────────────────────────
    st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)

    _chart_c1, _chart_c2 = st.columns(2)

    with _chart_c1:
        st.markdown('<div class="section-title">📊 Status Distribution</div>', unsafe_allow_html=True)
        _status_counts = df_display["Loop_Status"].value_counts()
        fig_status = go.Figure(go.Pie(
            labels=_status_counts.index.tolist(),
            values=_status_counts.values.tolist(),
            hole=0.55,
            marker=dict(colors=["#ff8c42", "#facc15", "#a78bfa", "#22c55e"]),
            textinfo="label+value",
            textfont=dict(size=11),
        ))
        fig_status.update_layout(
            height=320,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white", size=11),
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_status, use_container_width=True, config={"displayModeBar": False})

    with _chart_c2:
        st.markdown('<div class="section-title">🏭 Age Distribution by Product</div>', unsafe_allow_html=True)
        fig_age = go.Figure()
        for pt in sorted(df_display["Product_Type"].unique()):
            subset = df_display[df_display["Product_Type"] == pt]
            fig_age.add_trace(go.Histogram(
                x=subset["Age_Days"],
                name=pt,
                opacity=0.75,
                nbinsx=30,
            ))
        fig_age.add_vline(x=1551, line_dash="dash", line_color="#ef4444",
                         annotation_text="EU Limit (4.25y)", annotation_font_color="#ef4444")
        fig_age.update_layout(
            height=320,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white", size=11),
            margin=dict(l=40, r=10, t=10, b=40),
            xaxis=dict(title="Age (Days)", gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(title="Count", gridcolor="rgba(255,255,255,0.05)"),
            barmode="overlay",
            legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig_age, use_container_width=True, config={"displayModeBar": False})

    # ── Download button ───────────────────────────────────────────────────
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    _csv_data = df_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Filtered Assets (CSV)",
        data=_csv_data,
        file_name=f"asset_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="trk_download",
    )


