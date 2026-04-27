"""
modules/control_tower.py
------------------------
Control Tower — Executive intelligence hub + Multi-Agent War Room.

Section 1: Executive Dashboard
  - Today's snapshot: fleet health, risk alerts, top action items
  - Designed for management to absorb all critical info in  < 2 minutes

Section 2: Multi-Agent Meeting Room (War Room)
  - 4 AI agents discuss user questions in a "Zoom meeting" style:
    🔍 Data Validator, 📦 Inventory Agent, 🚛 Logistics Agent, 👔 Senior Manager
  - Each agent has a unique personality and expertise area
  - Conversation unfolds turn-by-turn so users see the deliberation process
"""
from __future__ import annotations

import os
import json
import time
import pandas as pd
import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SALES_PATH    = os.path.join(_BASE, "FINAL_Sales_QTY.csv")
_LOOPS_PATH    = os.path.join(_BASE, "FINAL_Documented_Loop_Times.csv")
_MFG_PATH      = os.path.join(_BASE, "FINAL_MFG_Date.csv")
_R2R_PATH      = os.path.join(_BASE, "FINAL_Receipt_to_Receipt_Data.csv")
_INSIGHTS_PATH = os.path.join(_BASE, "customer_insights.json")

# ── Agent Definitions ─────────────────────────────────────────────────────────
AGENTS = {
    "data_validator": {
        "name": "Alex — Data Validator",
        "emoji": "🔍",
        "color": "#38bdf8",
        "avatar": "🔍",
        "role": "Data Validator",
        "personality": (
            "You are Alex, a meticulous Data Validation Specialist. "
            "You focus on data integrity, checking if numbers add up, "
            "flagging inconsistencies, and verifying data quality. "
            "You speak precisely, cite specific data points, and are "
            "skeptical — you always verify before trusting any metric. "
            "Keep your responses to 2-3 sentences."
        ),
    },
    "inventory_agent": {
        "name": "Maya — Inventory Agent",
        "emoji": "📦",
        "color": "#a78bfa",
        "avatar": "📦",
        "role": "Inventory Strategist",
        "personality": (
            "You are Maya, an Inventory Optimization Strategist. "
            "You focus on fleet sizing, stock levels, container utilization, "
            "EU compliance (4.25-year rule), and optimal fleet allocation. "
            "You think in terms of safety stock, reorder points, and asset lifecycle. "
            "You give specific numbers and recommendations. "
            "Keep your responses to 2-3 sentences."
        ),
    },
    "logistics_agent": {
        "name": "Raj — Logistics Agent",
        "emoji": "🚛",
        "color": "#22c55e",
        "avatar": "🚛",
        "role": "Logistics Coordinator",
        "personality": (
            "You are Raj, a Logistics Operations Coordinator. "
            "You focus on transit times, dwell times, loop cycle efficiency, "
            "customer return patterns, and route optimization. "
            "You care about speed, delays, and bottlenecks in the supply chain loop. "
            "You suggest operational improvements. "
            "Keep your responses to 2-3 sentences."
        ),
    },
    "senior_manager": {
        "name": "Dr. Chen — Senior Manager",
        "emoji": "👔",
        "color": "#facc15",
        "avatar": "👔",
        "role": "VP Supply Chain",
        "personality": (
            "You are Dr. Chen, VP of Supply Chain. You speak LAST and synthesize "
            "what the other three agents said into a clear executive decision. "
            "You focus on business impact, ROI, customer relationships, and strategic priorities. "
            "You make the final recommendation based on the team's analysis. "
            "Start with 'Based on the team's analysis...' and be decisive. "
            "Keep your response to 2-3 sentences."
        ),
    },
}

AGENT_ORDER = ["data_validator", "inventory_agent", "logistics_agent", "senior_manager"]


# ── Data Loaders ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_control_data():
    """Load all data needed for the Control Tower dashboard."""
    from mfg_generator import sync_mfg_data
    from return_tracker import update_return_tracking

    sales = pd.read_csv(_SALES_PATH, parse_dates=["Date"])
    loops = pd.read_csv(_LOOPS_PATH)
    r2r = pd.read_csv(_R2R_PATH)
    mfg = sync_mfg_data(sales_path=_SALES_PATH, mfg_path=_MFG_PATH)
    fleet = update_return_tracking(sales, loops, mfg)

    insights = {}
    if os.path.exists(_INSIGHTS_PATH):
        try:
            with open(_INSIGHTS_PATH) as f:
                insights = json.load(f)
        except Exception:
            pass

    return sales, loops, r2r, mfg, fleet, insights


def _item_type(label: str) -> str:
    u = str(label).upper()
    if "1000L" in u:
        return "1000L Tote"
    if "55GAL" in u or "DR-55GAL" in u:
        return "55GAL Drum"
    if "330GAL" in u or "TT-330GAL" in u:
        return "330GAL Tote"
    return "Other"


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render():
    sales, loops, r2r, mfg, fleet, insights = _load_control_data()
    sales["Item Type"] = sales["Customer/Product"].apply(_item_type)

    _render_executive_dashboard(sales, loops, r2r, mfg, fleet, insights)

    st.markdown('<div style="height:40px;"></div>', unsafe_allow_html=True)

    _render_war_room(sales, loops, r2r, fleet, insights)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: EXECUTIVE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def _render_executive_dashboard(sales, loops, r2r, mfg, fleet, insights):
    st.markdown('''
    <div style="margin-bottom:8px;">
      <div style="font-size:2rem;font-weight:800;
                  background:linear-gradient(135deg,#38bdf8 0%,#a78bfa 50%,#f472b6 100%);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
        🏢 Control Tower
      </div>
      <div style="font-size:0.85rem;color:rgba(255,255,255,0.45);margin-top:2px;">
        Executive intelligence briefing — Everything you need in 2 minutes
      </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Row 1: Fleet Health Snapshot ──────────────────────────────────────
    total_fleet = len(fleet)
    green = int(fleet["Compliance"].str.contains("Green").sum())
    amber = total_fleet - green
    green_pct = round(100 * green / max(total_fleet, 1), 1)
    available = int((fleet["Loop_Code"] == "available").sum())
    at_customer = int((fleet["Loop_Code"] == "at_customer").sum())
    in_transit_out = int((fleet["Loop_Code"] == "in_transit_out").sum())
    in_transit_back = int((fleet["Loop_Code"] == "in_transit_back").sum())
    avg_age_days = int(fleet["Age_Days"].mean())
    avg_age_yrs = round(avg_age_days / 365, 1)

    # Total volume this month
    now = pd.Timestamp.now()
    this_month = sales[
        (sales["Date"].dt.year == now.year) & (sales["Date"].dt.month == now.month)
    ]
    month_vol = int(this_month["Quantity"].sum())
    total_vol = int(sales["Quantity"].sum())
    unique_customers = sales["Customer/Product"].str.split("(").str[0].str.strip().nunique()

    # EU expiring soon
    fleet["DUA"] = fleet["Age_Days"].apply(lambda x: max(0, 1551 - x))
    expire_30 = int((fleet["DUA"].between(1, 30)).sum())
    expire_90 = int((fleet["DUA"].between(1, 90)).sum())

    st.markdown('<div class="section-title" style="font-size:1rem;margin-top:16px;">'
                '📊 Fleet Health Snapshot</div>', unsafe_allow_html=True)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            Total Fleet</div>
          <div style="font-size:1.8rem;font-weight:800;color:white;">{total_fleet:,}</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">containers tracked</div>
        </div>''', unsafe_allow_html=True)
    with k2:
        _g_color = "#22c55e" if green_pct >= 50 else "#facc15" if green_pct >= 30 else "#ef4444"
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            EU Green Fleet</div>
          <div style="font-size:1.8rem;font-weight:800;color:{_g_color};">{green_pct}%</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">{green:,}G · {amber:,}A</div>
        </div>''', unsafe_allow_html=True)
    with k3:
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            Avg Fleet Age</div>
          <div style="font-size:1.8rem;font-weight:800;color:white;">{avg_age_yrs}y</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">{avg_age_days:,} days</div>
        </div>''', unsafe_allow_html=True)
    with k4:
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            Available Now</div>
          <div style="font-size:1.8rem;font-weight:800;color:#22c55e;">{available:,}</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">ready to ship</div>
        </div>''', unsafe_allow_html=True)
    with k5:
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            In Circulation</div>
          <div style="font-size:1.8rem;font-weight:800;color:#facc15;">{at_customer + in_transit_out + in_transit_back:,}</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">out + customer + returning</div>
        </div>''', unsafe_allow_html=True)
    with k6:
        _exp_color = "#ef4444" if expire_30 > 10 else "#facc15" if expire_30 > 0 else "#22c55e"
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.6);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:14px 16px;text-align:center;">
          <div style="font-size:0.6rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px;">
            EU Expiring Soon</div>
          <div style="font-size:1.8rem;font-weight:800;color:{_exp_color};">{expire_30}</div>
          <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">within 30 days</div>
        </div>''', unsafe_allow_html=True)

    # ── Row 2: Operational Pulse ──────────────────────────────────────────
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
    op1, op2, op3 = st.columns(3)

    with op1:
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.5);border:1px solid rgba(255,255,255,0.06);
                    border-radius:14px;padding:18px 20px;">
          <div style="font-size:0.85rem;font-weight:700;color:white;margin-bottom:10px;">
            📈 Demand Pulse</div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">Total Volume (All Time)</span>
            <span style="font-size:0.75rem;font-weight:700;color:white;">{total_vol:,} units</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">This Month</span>
            <span style="font-size:0.75rem;font-weight:700;color:#38bdf8;">{month_vol:,} units</span>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">Active Customers</span>
            <span style="font-size:0.75rem;font-weight:700;color:#a78bfa;">{unique_customers}</span>
          </div>
        </div>''', unsafe_allow_html=True)

    with op2:
        r2r_median = round(r2r["R2R Days (median)"].mean(), 1)
        avg_loop = round(loops["Total Transit Time (Days)"].mean(), 1)
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.5);border:1px solid rgba(255,255,255,0.06);
                    border-radius:14px;padding:18px 20px;">
          <div style="font-size:0.85rem;font-weight:700;color:white;margin-bottom:10px;">
            🔄 Loop Efficiency</div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">Avg Loop Time</span>
            <span style="font-size:0.75rem;font-weight:700;color:white;">{avg_loop} days</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">R2R Median</span>
            <span style="font-size:0.75rem;font-weight:700;color:#facc15;">{r2r_median} days</span>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="font-size:0.75rem;color:rgba(255,255,255,0.5);">Containers / Customer</span>
            <span style="font-size:0.75rem;font-weight:700;color:#22c55e;">
              {round(total_fleet / max(unique_customers, 1), 1)}</span>
          </div>
        </div>''', unsafe_allow_html=True)

    with op3:
        # Product mix
        product_counts = sales.groupby("Item Type")["Quantity"].sum().sort_values(ascending=False)
        prod_rows = ""
        _colors = {"1000L Tote": "#38bdf8", "55GAL Drum": "#facc15",
                    "330GAL Tote": "#a78bfa", "Other": "#8892b0"}
        for pt, qty in product_counts.items():
            c = _colors.get(pt, "#8892b0")
            pct = round(100 * qty / max(total_vol, 1))
            prod_rows += (
                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                f'<span style="font-size:0.75rem;color:{c};font-weight:600;">{pt}</span>'
                f'<span style="font-size:0.75rem;color:rgba(255,255,255,0.6);">'
                f'{qty:,} ({pct}%)</span></div>'
            )
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.5);border:1px solid rgba(255,255,255,0.06);
                    border-radius:14px;padding:18px 20px;">
          <div style="font-size:0.85rem;font-weight:700;color:white;margin-bottom:10px;">
            📦 Product Mix</div>
          {prod_rows}
        </div>''', unsafe_allow_html=True)

    # ── Row 3: Risk Alerts ────────────────────────────────────────────────
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="font-size:1rem;">'
                '⚠️ Active Risk Alerts</div>', unsafe_allow_html=True)

    alerts = []
    # Fleet age risk
    if green_pct < 40:
        alerts.append(("🔴", "Critical", f"Green fleet at {green_pct}% — below 40% threshold. "
                        f"{amber:,} Amber containers restricted to domestic only."))
    elif green_pct < 50:
        alerts.append(("🟡", "Warning", f"Green fleet at {green_pct}% — approaching critical. "
                        f"Monitor EU compliance closely."))
    # Expiry
    if expire_30 > 0:
        alerts.append(("🟡", "Expiring", f"{expire_30} containers turning Amber within 30 days, "
                        f"{expire_90} within 90 days."))
    # Avg fleet age
    if avg_age_yrs > 4.0:
        alerts.append(("🔴", "Aging Fleet", f"Average fleet age is {avg_age_yrs} years — "
                        "dangerously close to the 4.25-year EU limit."))
    # Low available
    avail_pct = round(100 * available / max(total_fleet, 1))
    if avail_pct < 50:
        alerts.append(("🟡", "Capacity", f"Only {avail_pct}% of fleet available. "
                        f"{total_fleet - available:,} containers are in circulation."))
    if not alerts:
        alerts.append(("🟢", "All Clear", "No critical risks detected. Fleet is healthy."))

    for icon, severity, msg in alerts:
        _sev_color = {"Critical": "#ef4444", "Warning": "#facc15", "Expiring": "#f97316",
                      "Aging Fleet": "#ef4444", "Capacity": "#facc15",
                      "All Clear": "#22c55e"}.get(severity, "#888")
        st.markdown(f'''
        <div style="background:rgba(30,32,40,0.4);border-left:4px solid {_sev_color};
                    border-radius:8px;padding:10px 14px;margin-bottom:8px;
                    display:flex;align-items:center;gap:10px;">
          <span style="font-size:1.2rem;">{icon}</span>
          <div>
            <span style="font-size:0.75rem;font-weight:700;color:{_sev_color};
                        text-transform:uppercase;letter-spacing:0.5px;">{severity}</span>
            <div style="font-size:0.78rem;color:rgba(255,255,255,0.6);margin-top:2px;">{msg}</div>
          </div>
        </div>''', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: MULTI-AGENT WAR ROOM
# ══════════════════════════════════════════════════════════════════════════════

def _render_war_room(sales, loops, r2r, fleet, insights):
    st.markdown('''
    <div style="margin-top:30px;margin-bottom:12px;">
      <div style="font-size:1.4rem;font-weight:800;color:white;display:flex;align-items:center;gap:10px;">
        <span style="font-size:1.6rem;">🎙️</span>
        Multi-Agent War Room
      </div>
      <div style="font-size:0.8rem;color:rgba(255,255,255,0.4);margin-top:4px;">
        Ask a question and watch 4 specialized AI agents discuss it in real-time — like a Zoom meeting for your supply chain team
      </div>
    </div>
    ''', unsafe_allow_html=True)

    # Show agent cards
    a1, a2, a3, a4 = st.columns(4)
    for col, agent_key in zip([a1, a2, a3, a4], AGENT_ORDER):
        ag = AGENTS[agent_key]
        with col:
            st.markdown(f'''
            <div style="background:rgba(30,32,40,0.5);border:1px solid {ag["color"]}30;
                        border-radius:12px;padding:14px 16px;text-align:center;
                        border-top:3px solid {ag["color"]};">
              <div style="font-size:1.8rem;margin-bottom:4px;">{ag["emoji"]}</div>
              <div style="font-size:0.78rem;font-weight:700;color:{ag["color"]};">{ag["role"]}</div>
              <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);margin-top:2px;">
                {ag["name"].split("—")[0].strip()}</div>
            </div>''', unsafe_allow_html=True)

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

    # ── Question input ────────────────────────────────────────────────────
    user_q = st.text_input(
        "💬 Ask the War Room a question",
        placeholder="e.g. Should we invest in more 330GAL Totes or focus on 55GAL Drums?",
        key="war_room_question",
    )

    q_col1, q_col2 = st.columns([3, 1])
    with q_col1:
        start_meeting = st.button(
            "🚀 Start Meeting", type="primary",
            use_container_width=True, key="war_room_start"
        )
    with q_col2:
        if st.button("🗑️ Clear", use_container_width=True, key="war_room_clear"):
            st.session_state.pop("war_room_messages", None)
            st.session_state.pop("war_room_question", None)
            st.rerun()

    # ── Check API key ─────────────────────────────────────────────────────
    has_key = bool(st.session_state.get("gemini_key"))

    # ── Display previous conversation ─────────────────────────────────────
    if "war_room_messages" in st.session_state and st.session_state.war_room_messages:
        _render_meeting_transcript(st.session_state.war_room_messages)

    # ── Run new meeting ───────────────────────────────────────────────────
    if start_meeting and user_q.strip():
        if not has_key:
            st.warning("⚠️ Please connect your API key in the Möbius AI panel below first.")
            return

        # Build compact data context for agents
        total_fleet = len(fleet)
        green = int(fleet["Compliance"].str.contains("Green").sum())
        available = int((fleet["Loop_Code"] == "available").sum())
        avg_loop = round(loops["Total Transit Time (Days)"].mean(), 1)

        data_brief = (
            f"Fleet: {total_fleet:,} containers ({green:,} Green, {total_fleet-green:,} Amber). "
            f"Available: {available:,}. Avg loop time: {avg_loop}d. "
            f"Avg fleet age: {int(fleet['Age_Days'].mean())}d ({round(fleet['Age_Days'].mean()/365,1)}y). "
            f"Products: {sales.groupby('Item Type')['Quantity'].sum().to_dict()}. "
            f"Total customers: {sales['Customer/Product'].str.split('(').str[0].str.strip().nunique()}. "
            f"R2R median: {round(r2r['R2R Days (median)'].mean(),1)}d."
        )

        messages = []
        meeting_container = st.container()

        with meeting_container:
            # User question header
            st.markdown(f'''
            <div style="background:rgba(56,189,248,0.06);border:1px solid rgba(56,189,248,0.15);
                        border-radius:12px;padding:14px 18px;margin-bottom:16px;">
              <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);text-transform:uppercase;
                          letter-spacing:0.5px;margin-bottom:4px;">📋 Meeting Agenda</div>
              <div style="font-size:0.9rem;color:white;font-weight:600;">{user_q}</div>
            </div>''', unsafe_allow_html=True)

            messages.append({"role": "user", "content": user_q})

            # Each agent speaks in turn
            prior_responses = ""
            for agent_key in AGENT_ORDER:
                ag = AGENTS[agent_key]

                # Show "thinking" indicator
                thinking_ph = st.empty()
                thinking_ph.markdown(f'''
                <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;
                            background:rgba(255,255,255,0.02);border-radius:10px;margin-bottom:8px;">
                  <span style="font-size:1.4rem;">{ag["emoji"]}</span>
                  <div>
                    <span style="font-size:0.78rem;font-weight:700;color:{ag["color"]};">
                      {ag["name"]}</span>
                    <span style="font-size:0.72rem;color:rgba(255,255,255,0.3);margin-left:8px;">
                      is thinking...</span>
                  </div>
                </div>''', unsafe_allow_html=True)

                try:
                    response_text = _call_agent(
                        agent_key=agent_key,
                        question=user_q,
                        data_brief=data_brief,
                        prior_responses=prior_responses,
                    )
                except Exception as e:
                    response_text = f"⚠️ Error: {str(e)[:100]}"

                # Replace thinking with actual response
                thinking_ph.empty()
                _render_agent_message(ag, response_text)

                messages.append({
                    "role": agent_key,
                    "agent": ag["name"],
                    "emoji": ag["emoji"],
                    "color": ag["color"],
                    "content": response_text,
                })
                prior_responses += f"\n{ag['name']}: {response_text}"

            # Save conversation
            st.session_state.war_room_messages = messages

    elif start_meeting and not user_q.strip():
        st.warning("Please type a question first.")


def _render_agent_message(ag: dict, text: str):
    """Render a single agent's message bubble."""
    st.markdown(f'''
    <div style="display:flex;gap:12px;padding:12px 16px;
                background:rgba(255,255,255,0.02);border:1px solid {ag["color"]}15;
                border-radius:12px;margin-bottom:10px;
                border-left:3px solid {ag["color"]};">
      <div style="flex:0 0 40px;text-align:center;">
        <div style="font-size:1.6rem;">{ag["emoji"]}</div>
      </div>
      <div style="flex:1;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
          <span style="font-size:0.78rem;font-weight:700;color:{ag["color"]};">
            {ag["name"]}</span>
          <span style="font-size:0.6rem;color:rgba(255,255,255,0.25);
                      background:rgba(255,255,255,0.04);padding:1px 6px;border-radius:4px;">
            {ag["role"]}</span>
        </div>
        <div style="font-size:0.82rem;color:rgba(255,255,255,0.7);line-height:1.6;">
          {text}
        </div>
      </div>
    </div>''', unsafe_allow_html=True)


def _render_meeting_transcript(messages: list):
    """Render a saved meeting transcript."""
    st.markdown('''
    <div style="font-size:0.75rem;color:rgba(255,255,255,0.3);margin-bottom:8px;
                text-transform:uppercase;letter-spacing:0.5px;">
      📝 Previous Meeting Transcript
    </div>''', unsafe_allow_html=True)

    for msg in messages:
        if msg["role"] == "user":
            st.markdown(f'''
            <div style="background:rgba(56,189,248,0.06);border:1px solid rgba(56,189,248,0.15);
                        border-radius:12px;padding:12px 16px;margin-bottom:12px;">
              <div style="font-size:0.65rem;color:rgba(255,255,255,0.35);">📋 Question</div>
              <div style="font-size:0.85rem;color:white;font-weight:600;">{msg["content"]}</div>
            </div>''', unsafe_allow_html=True)
        else:
            ag = {
                "emoji": msg.get("emoji", "🤖"),
                "color": msg.get("color", "#888"),
                "name": msg.get("agent", "Agent"),
                "role": AGENTS.get(msg["role"], {}).get("role", "Agent"),
            }
            _render_agent_message(ag, msg["content"])


# ── Private: Call a single agent via Gemini ───────────────────────────────────

def _call_agent(
    agent_key: str,
    question: str,
    data_brief: str,
    prior_responses: str,
) -> str:
    """Call Gemini API with a specific agent persona."""
    import google.generativeai as genai

    genai.configure(api_key=st.session_state["gemini_key"])

    selected_model = "gemini-pro"
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                selected_model = m.name
                break
    except Exception:
        pass

    model = genai.GenerativeModel(selected_model)
    ag = AGENTS[agent_key]

    system_prompt = (
        f"{ag['personality']}\n\n"
        f"You are in a multi-agent supply chain meeting for MLI (a chemical packaging company). "
        f"The company manages returnable containers (1000L Totes, 330GAL Totes, 55GAL Drums). "
        f"Containers have a 4.25-year EU compliance limit (Green < 4.25y, Amber > 4.25y). "
        f"\n\n[CURRENT DATA SNAPSHOT]\n{data_brief}"
    )

    if prior_responses:
        system_prompt += f"\n\n[WHAT OTHER AGENTS SAID BEFORE YOU]\n{prior_responses}"

    prompt = f"{system_prompt}\n\n[USER QUESTION]\n{question}"

    response = model.generate_content(prompt)
    return response.text
