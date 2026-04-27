"""
ai_context.py
-------------
Builds the full database context payload for the MLI Fleet Intelligence AI.

Loads data from:
  - customer_insights.json  — per-customer aggregated metrics + order history + anomalies
  - item_metrics.json       — per-product simulation defaults
  - anomaly_archive.json    — analyst-classified anomaly records
  - MLI Capstone Data.xlsx  — raw contract & R2R sheet slices

Keeps token usage manageable by:
  - Sending ALL customers' aggregated profiles (compact dict per customer)
  - Sending the FULL order history only for the currently focused deep-dive customer
  - Sending raw contract rows only for customers matching the selected product
  - Capping anomaly archive at the most recent 50 entries
"""

from __future__ import annotations
import json
import os
import pandas as pd

# ── File paths (from central config) ──────────────────────────────────────────
from config import (
    CUSTOMER_INSIGHTS_PATH, ITEM_METRICS_PATH,
    DATA_FILE_PATH as EXCEL_PATH,
    SHEET_CONTRACTS, SHEET_R2R,
)


def _safe_load_json(path: str):
    """Load a JSON file, returning None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _load_contracts() -> list[dict]:
    """Load the Documented Loop Times sheet as a list of compact dicts."""
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_CONTRACTS)
        df.columns = [str(c).strip() for c in df.columns]
        rows = []
        for _, row in df.iterrows():
            rows.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
        return rows
    except Exception:
        return []


def _load_r2r() -> list[dict]:
    """Load the Receipt-to-Receipt sheet as a list of compact dicts."""
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_R2R)
        df.columns = [str(c).strip() for c in df.columns]
        rows = []
        for _, row in df.iterrows():
            rows.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
        return rows
    except Exception:
        return []


def build_ai_context(
    selected_item: str,
    focused_customer: str | None,
    page_state: dict,
    archive: list[dict],
) -> dict:
    """
    Build a comprehensive context dict to inject into the AI prompt.

    Args:
        selected_item     : Currently selected product (e.g. "55GAL Drum")
        focused_customer  : Customer currently open in the deep-dive panel (or None)
        page_state        : Dict of live dashboard values (sidebar params, sim results, global stats)
        archive           : List of resolved anomaly archive entries

    Returns:
        A dict ready to be serialised via json.dumps() into the AI prompt.
    """
    all_insights  = _safe_load_json(CUSTOMER_INSIGHTS_PATH) or {}
    all_metrics   = _safe_load_json(ITEM_METRICS_PATH) or {}
    contracts     = _load_contracts()
    r2r_data      = _load_r2r()

    # ── Per-product summaries (all products, compact) ─────────────────────────
    products_summary = {}
    for product, customers in all_insights.items():
        metrics = all_metrics.get(product, {})
        products_summary[product] = {
            "daily_demand":    metrics.get("daily_demand"),
            "dwell_mean_days": metrics.get("dwell_mean"),
            "known_fleet_size": metrics.get("fleet_size"),
            "customer_count":  len(customers),
            "total_annual_qty": sum(c.get("annual_qty", 0) or 0 for c in customers),
        }

    # ── All customers for the current product (aggregated, no raw history) ────
    current_product_customers = []
    for c in all_insights.get(selected_item, []):
        avg_dwell  = c.get("avg_dwell_time")
        contracted = c.get("doc_total_time")
        variance   = (
            round(avg_dwell - contracted, 1)
            if isinstance(avg_dwell, (int, float)) and isinstance(contracted, (int, float))
            else None
        )
        current_product_customers.append({
            "customer":          c.get("customer"),
            "annual_qty":        c.get("annual_qty"),
            "avg_monthly_units": c.get("avg_monthly_units"),
            "frequency":         c.get("frequency_label"),
            "active_months":     c.get("active_months"),
            "avg_dwell_days":    avg_dwell,
            "contracted_days":   contracted,
            "dwell_variance":    variance,
            "consignment_max":   c.get("doc_consignment_max"),
            "daily_consumption": c.get("doc_daily_consumption"),
            "anomaly_count":     len(c.get("anomalies", [])),
            "anomalies":         c.get("anomalies", []),  # keep anomaly list (compact)
            "is_deep_dive":      c.get("customer") == focused_customer,
        })

    # ── Full order history for the focused customer only ──────────────────────
    focused_history = []
    if focused_customer:
        for c in all_insights.get(selected_item, []):
            if c.get("customer") == focused_customer:
                focused_history = c.get("history", [])
                break

    # ── Unresolved anomalies across ALL products ──────────────────────────────
    from anomaly_manager import get_archived_ids
    archived_ids = get_archived_ids()
    all_unresolved = [
        {
            "product":   product,
            "customer":  c.get("customer"),
            "date":      a["date"],
            "qty":       a["qty"],
            "z_score":   a["z_score"],
        }
        for product, customers in all_insights.items()
        for c in customers
        for a in c.get("anomalies", [])
        if f"{c.get('customer')}__{product}__{a['date']}".lower().replace(" ", "_")
           not in archived_ids
    ]

    return {
        "page_state":     page_state,
        "all_products":   products_summary,
        "current_product": {
            "name":      selected_item,
            "metrics":   all_metrics.get(selected_item, {}),
            "customers": current_product_customers,
        },
        "focused_customer_full_history": {
            "customer": focused_customer,
            "history":  focused_history,   # Complete order-by-order history
        } if focused_customer else None,
        "raw_contracts":          contracts,        # All contract rows from Excel
        "r2r_data":               r2r_data,         # Receipt-to-receipt data
        "unresolved_anomalies":   all_unresolved,
        "anomaly_archive":        archive[-50:],    # Last 50 resolved entries
    }
