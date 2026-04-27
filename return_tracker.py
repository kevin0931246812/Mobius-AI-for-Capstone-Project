"""
return_tracker.py
-----------------
Live Twin Engine — Layer 3 & 4
Dynamic Asset Tracking and Compliance-Aware Allocation.

Layer 3: Loop Status — uses quantity-based flow modeling to distribute assets
         across loop stages based on shipment volumes and transit times.
Layer 4: Compliance — classifies assets by EU age limit (1,551 days / 4.25 yrs),
         then allocates Green→International, Amber→Domestic.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import os
import datetime
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Constants ─────────────────────────────────────────────────────────────────
EU_AGE_LIMIT_DAYS = 1551            # 4.25 years in days
INTERNATIONAL_DEMAND_PCT = 0.20     # 20% of demand is international/EU
DOMESTIC_DEMAND_PCT = 0.80          # 80% is domestic


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3: Dynamic Asset Tracking — Loop Status (Quantity-Based Flow)
# ══════════════════════════════════════════════════════════════════════════════

def _build_transit_lookup(df_loops: pd.DataFrame) -> dict:
    """
    Build a lookup dict keyed by FG part substring → {to_customer, dwell, to_mli, total}.
    Also keeps a raw-name key so we can match flexibly.
    Returns list of (key_variants, transit_dict) for priority matching.
    """
    entries = []
    for _, row in df_loops.iterrows():
        raw_name = str(row["Customer Name"]).strip()
        t = {
            "to_customer": int(row.get("Transit Time to Customer Site (Days)", 7)),
            "to_mli":      int(row.get("Transit Time to MLI (Days)", 7)),
            "dwell":       int(row.get("Any other touch points? (empties at warehouse) (Days)", 30)),
            "total":       int(row.get("Total Transit Time (Days)", 60)),
            "doi_min":     float(row.get("DOI Min at CS Site", 14)),
            "doi_max":     float(row.get("DOI Max at CS Site", 30)),
            "route_name":  raw_name,
        }
        entries.append((raw_name, t))
    return entries


def _match_transit(fg_part: str, customer: str, entries: list, default: dict) -> dict:
    """
    Match an asset's FG part number or customer name to its transit profile.
    Priority: exact FG part match > customer name substring match > default.
    If multiple matches, average them to get a representative transit profile.
    """
    fg_clean = str(fg_part).strip()
    cust_clean = str(customer).strip()

    # Priority 1: Match by FG part — the FG part often appears in the loop entry
    fg_matches = []
    for raw_name, t in entries:
        # Check if FG part prefix appears in the route name
        fg_prefix = fg_clean.split("(")[0].strip()  # e.g. "CustomerQ25TUP2-A"
        if fg_prefix and fg_prefix in raw_name:
            fg_matches.append(t)

    if fg_matches:
        # Average across matching routes for this FG part
        return {
            "to_customer": int(np.mean([m["to_customer"] for m in fg_matches])),
            "to_mli":      int(np.mean([m["to_mli"] for m in fg_matches])),
            "dwell":       int(np.mean([m["dwell"] for m in fg_matches])),
            "total":       int(np.mean([m["total"] for m in fg_matches])),
            "route_name":  fg_matches[0]["route_name"],
        }

    # Priority 2: Match by customer name substring (e.g. "Customer W" in "CustomerW25TUP2")
    cust_matches = []
    cust_letter = cust_clean.replace("Customer ", "").strip()  # e.g. "Q", "W"
    for raw_name, t in entries:
        if f"Customer {cust_letter}" in raw_name or f"Customer{cust_letter}" in raw_name:
            cust_matches.append(t)
    if cust_matches:
        return {
            "to_customer": int(np.mean([m["to_customer"] for m in cust_matches])),
            "to_mli":      int(np.mean([m["to_mli"] for m in cust_matches])),
            "dwell":       int(np.mean([m["dwell"] for m in cust_matches])),
            "total":       int(np.mean([m["total"] for m in cust_matches])),
            "route_name":  cust_matches[0]["route_name"],
        }

    return default


def update_return_tracking(
    df_sales: pd.DataFrame,
    df_loops: pd.DataFrame,
    df_mfg: pd.DataFrame,
    as_of: Optional[datetime.date] = None,
) -> pd.DataFrame:
    """
    Calculate Loop Status for every asset using quantity-based flow modeling.

    Uses real shipment dates to determine which stage each asset is in:
      Stage 1: In Inventory (available at MLI)
      Stage 2: In-Transit to Customer (shipped within last T_to_customer days)
      Stage 3: At Customer (shipped T_to_customer..T_to_customer+dwell days ago)
      Stage 4: Returning to MLI (shipped T_to_customer+dwell..T_total days ago)

    Each asset stores its transit breakdown and the last order date so
    the UI can display a live pipeline timeline.
    """
    today = pd.Timestamp(as_of or datetime.date.today())

    # Build transit time lookup
    transit_entries = _build_transit_lookup(df_loops)
    default_transit = {"to_customer": 7, "to_mli": 7, "dwell": 30, "total": 60,
                       "route_name": "Default"}

    # Parse MFG data
    mfg = df_mfg.copy()
    mfg["MFG DATE"] = pd.to_datetime(mfg["MFG DATE"], errors="coerce")
    mfg["Age_Days"] = (today - mfg["MFG DATE"]).dt.days

    # Age compliance classification
    mfg["Compliance"] = np.where(
        mfg["Age_Days"] <= EU_AGE_LIMIT_DAYS, "🟢 Green", "🟡 Amber"
    )
    mfg["Compliance_Label"] = np.where(
        mfg["Age_Days"] <= EU_AGE_LIMIT_DAYS, "EU-Compliant", "Domestic-Only"
    )

    # Parse sales data
    sales = df_sales.copy()
    sales["Date"] = pd.to_datetime(sales["Date"], errors="coerce")
    sales["Days_Ago"] = (today - sales["Date"]).dt.days
    sales["Cust_Clean"] = sales["Customer/Product"].str.split("(").str[0].str.strip()

    # Group MFG assets by customer
    mfg_by_cust = mfg.groupby("Customer")

    all_statuses = []

    for cust_name, cust_assets in mfg_by_cust:
        cust_str = str(cust_name).strip()
        n_assets = len(cust_assets)

        # Get the FG part for this customer group to find transit profile
        sample_fg = str(cust_assets.iloc[0].get("FG part number", ""))
        t = _match_transit(sample_fg, cust_str, transit_entries, default_transit)

        # Find recent sales for this customer using FG part matching
        cust_sales = pd.DataFrame()
        fg_prefix = sample_fg.split("(")[0].strip()
        for ship_cust in sales["Customer/Product"].unique():
            ship_clean = str(ship_cust).split("(")[0].strip()
            # Match if FG prefix is in the sales customer name, or customer letter matches
            if fg_prefix and fg_prefix in ship_clean:
                matched = sales[sales["Customer/Product"] == ship_cust]
                cust_sales = pd.concat([cust_sales, matched])
            else:
                cust_letter = cust_str.replace("Customer ", "").strip()
                if len(cust_letter) <= 2 and (f"Customer {cust_letter} " in ship_cust or
                    f"Customer{cust_letter}" in ship_cust):
                    matched = sales[sales["Customer/Product"] == ship_cust]
                    cust_sales = pd.concat([cust_sales, matched])

        # Find last order date for this customer
        last_order_date = None
        if not cust_sales.empty:
            last_order_date = cust_sales["Date"].max()

        # Count quantities shipped in each time window
        if not cust_sales.empty:
            w1 = cust_sales[cust_sales["Days_Ago"].between(0, t["to_customer"])]
            qty_transit_out = int(w1["Quantity"].sum())

            w2 = cust_sales[cust_sales["Days_Ago"].between(
                t["to_customer"] + 1, t["to_customer"] + t["dwell"]
            )]
            qty_at_customer = int(w2["Quantity"].sum())

            w3 = cust_sales[cust_sales["Days_Ago"].between(
                t["to_customer"] + t["dwell"] + 1, t["total"]
            )]
            qty_transit_back = int(w3["Quantity"].sum())
        else:
            qty_transit_out = 0
            qty_at_customer = 0
            qty_transit_back = 0

        # Cap total deployed to not exceed assets for this customer
        total_deployed = qty_transit_out + qty_at_customer + qty_transit_back
        if total_deployed > n_assets:
            scale = n_assets / total_deployed
            qty_transit_out = int(qty_transit_out * scale)
            qty_at_customer = int(qty_at_customer * scale)
            qty_transit_back = int(qty_transit_back * scale)

        qty_available = max(0, n_assets - qty_transit_out - qty_at_customer - qty_transit_back)

        # Build status assignment — assign shipped assets by recency
        # Most recently shipped → in_transit_out, then at_customer, etc.
        status_labels = (
            ["🚛 In-Transit to Customer"] * qty_transit_out +
            ["📦 At Customer"] * qty_at_customer +
            ["🔄 In-Transit to MLI"] * qty_transit_back +
            ["✅ Available"] * qty_available
        )
        status_codes = (
            ["in_transit_out"] * qty_transit_out +
            ["at_customer"] * qty_at_customer +
            ["in_transit_back"] * qty_transit_back +
            ["available"] * qty_available
        )

        # Build per-status order dates (approximate)
        order_dates = []
        if not cust_sales.empty:
            sorted_sales = cust_sales.sort_values("Date", ascending=False)
            # Assign most recent orders to transit_out, then at_customer, etc.
            all_orders = []
            for _, s_row in sorted_sales.iterrows():
                for _ in range(int(s_row["Quantity"])):
                    all_orders.append(s_row["Date"])

            idx = 0
            for _ in range(qty_transit_out):
                order_dates.append(all_orders[idx] if idx < len(all_orders) else last_order_date)
                idx += 1
            for _ in range(qty_at_customer):
                order_dates.append(all_orders[idx] if idx < len(all_orders) else last_order_date)
                idx += 1
            for _ in range(qty_transit_back):
                order_dates.append(all_orders[idx] if idx < len(all_orders) else last_order_date)
                idx += 1
            for _ in range(qty_available):
                order_dates.append(pd.NaT)  # Available = no active order
        else:
            order_dates = [pd.NaT] * n_assets

        # Pad or trim lists
        while len(status_labels) < n_assets:
            status_labels.append("✅ Available")
            status_codes.append("available")
            order_dates.append(pd.NaT)
        status_labels = status_labels[:n_assets]
        status_codes = status_codes[:n_assets]
        order_dates = order_dates[:n_assets]

        # Shuffle assets so Green/Amber are randomly distributed across statuses
        asset_list = cust_assets.sample(frac=1, random_state=42).reset_index(drop=True)

        for i, (_, row) in enumerate(asset_list.iterrows()):
            code = status_codes[i]
            odate = order_dates[i]

            # Calculate days elapsed in current stage and days remaining
            if pd.notna(odate):
                days_since_order = (today - odate).days
            else:
                days_since_order = 0

            # Expected arrival dates based on order date
            if pd.notna(odate):
                arrive_customer = odate + pd.Timedelta(days=t["to_customer"])
                leave_customer  = odate + pd.Timedelta(days=t["to_customer"] + t["dwell"])
                arrive_mli      = odate + pd.Timedelta(days=t["total"])
            else:
                arrive_customer = pd.NaT
                leave_customer  = pd.NaT
                arrive_mli      = pd.NaT

            # Days until return to MLI
            if pd.notna(arrive_mli) and code != "available":
                days_until_return = max(0, (arrive_mli - today).days)
            else:
                days_until_return = 0

            all_statuses.append({
                "Serial": row.get("Serial number", ""),
                "Customer": cust_str,
                "Item": row.get("Item number", ""),
                "FG_Part": row.get("FG part number", ""),
                "MFG_Date": row.get("MFG DATE"),
                "Age_Days": row.get("Age_Days", 0),
                "Compliance": row.get("Compliance", "🟡 Amber"),
                "Compliance_Label": row.get("Compliance_Label", "Domestic-Only"),
                "Loop_Status": status_labels[i],
                "Loop_Code": status_codes[i],
                "Transit_Total": t["total"],
                "Transit_To_Cust": t["to_customer"],
                "Transit_Dwell": t["dwell"],
                "Transit_To_MLI": t["to_mli"],
                "Order_Date": odate,
                "Days_Since_Order": days_since_order,
                "ETA_At_Customer": arrive_customer,
                "ETA_Leave_Customer": leave_customer,
                "ETA_Return_MLI": arrive_mli,
                "Days_Until_Return": days_until_return,
            })

    return pd.DataFrame(all_statuses)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4: Compliance-Aware Allocation
# ══════════════════════════════════════════════════════════════════════════════

def assign_destination(fleet_df: pd.DataFrame, total_demand: int = 0) -> dict:
    """
    Allocate available assets to International (20%) vs Domestic (80%) demand.

    Rules:
      - International orders MUST use Green (EU-compliant) assets only.
      - Domestic orders can use either Green or Amber.
      - If not enough Green assets for international, flag Compliance Stockout.

    Returns a summary dict with allocation results and risk flags.
    """
    available = fleet_df[fleet_df["Loop_Code"] == "available"]
    green_available = available[available["Compliance"].str.contains("Green")]
    amber_available = available[available["Compliance"].str.contains("Amber")]

    total_available = len(available)
    green_count = len(green_available)
    amber_count = len(amber_available)

    # Demand split — use total available as proxy if no explicit demand
    if total_demand <= 0:
        total_demand = total_available

    intl_demand = int(np.ceil(total_demand * INTERNATIONAL_DEMAND_PCT))
    domestic_demand = total_demand - intl_demand

    # Allocation
    intl_filled = min(intl_demand, green_count)
    intl_gap = max(0, intl_demand - green_count)

    # Domestic can use remaining green + all amber
    remaining_green = green_count - intl_filled
    domestic_pool = remaining_green + amber_count
    domestic_filled = min(domestic_demand, domestic_pool)
    domestic_gap = max(0, domestic_demand - domestic_pool)

    # Risk flags
    compliance_stockout = intl_gap > 0
    fleet_age_risk = (amber_count / max(total_available, 1)) > 0.60

    # How many days until next assets cross the EU limit?
    green_assets = fleet_df[fleet_df["Compliance"].str.contains("Green")].copy()
    if not green_assets.empty:
        green_assets["Days_Until_Amber"] = EU_AGE_LIMIT_DAYS - green_assets["Age_Days"]
        assets_expiring_30d = int((green_assets["Days_Until_Amber"] <= 30).sum())
        assets_expiring_90d = int((green_assets["Days_Until_Amber"] <= 90).sum())
        next_expiry_days = int(green_assets["Days_Until_Amber"].min())
    else:
        assets_expiring_30d = 0
        assets_expiring_90d = 0
        next_expiry_days = 0

    return {
        # Fleet overview
        "total_fleet": len(fleet_df),
        "total_available": total_available,
        "green_total": int(fleet_df["Compliance"].str.contains("Green").sum()),
        "amber_total": int(fleet_df["Compliance"].str.contains("Amber").sum()),
        "green_available": green_count,
        "amber_available": amber_count,

        # Loop status breakdown
        "in_transit_out": int((fleet_df["Loop_Code"] == "in_transit_out").sum()),
        "at_customer":    int((fleet_df["Loop_Code"] == "at_customer").sum()),
        "in_transit_back": int((fleet_df["Loop_Code"] == "in_transit_back").sum()),
        "available":      total_available,

        # Allocation
        "intl_demand": intl_demand,
        "intl_filled": intl_filled,
        "intl_gap": intl_gap,
        "domestic_demand": domestic_demand,
        "domestic_filled": domestic_filled,
        "domestic_gap": domestic_gap,

        # Risk assessment
        "compliance_stockout": compliance_stockout,
        "fleet_age_risk": fleet_age_risk,
        "fleet_green_pct": round(100 * green_count / max(total_available, 1), 1),
        "assets_expiring_30d": assets_expiring_30d,
        "assets_expiring_90d": assets_expiring_90d,
        "next_expiry_days": next_expiry_days,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Combined entry point
# ══════════════════════════════════════════════════════════════════════════════

def get_fleet_status(
    df_sales: pd.DataFrame,
    df_loops: pd.DataFrame,
    df_mfg: pd.DataFrame,
    as_of: Optional[datetime.date] = None,
    total_demand: int = 0,
) -> tuple[pd.DataFrame, dict]:
    """
    Full pipeline: tracking + allocation.

    Returns:
        (fleet_df, allocation_summary)
    """
    fleet = update_return_tracking(df_sales, df_loops, df_mfg, as_of)
    allocation = assign_destination(fleet, total_demand)
    return fleet, allocation


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    sales = pd.read_csv(os.path.join(BASE_DIR, "FINAL_Sales_QTY.csv"), parse_dates=["Date"])
    loops = pd.read_csv(os.path.join(BASE_DIR, "FINAL_Documented_Loop_Times.csv"))
    mfg   = pd.read_csv(os.path.join(BASE_DIR, "FINAL_MFG_Date.csv"))

    fleet, alloc = get_fleet_status(sales, loops, mfg)

    print("─" * 60)
    print("  LIVE TWIN ENGINE — Return Tracking Report")
    print("─" * 60)
    print(f"\n📊 Fleet Overview ({alloc['total_fleet']} assets):")
    print(f"   🟢 Green (EU-OK):   {alloc['green_total']}")
    print(f"   🟡 Amber (DOM-only): {alloc['amber_total']}")

    print(f"\n🔄 Loop Status:")
    print(f"   🚛 In-Transit Out:  {alloc['in_transit_out']}")
    print(f"   📦 At Customer:     {alloc['at_customer']}")
    print(f"   🔄 In-Transit Back: {alloc['in_transit_back']}")
    print(f"   ✅ Available:       {alloc['available']}")

    print(f"\n📋 Allocation (20/80 Split):")
    print(f"   International: {alloc['intl_filled']}/{alloc['intl_demand']} (gap: {alloc['intl_gap']})")
    print(f"   Domestic:      {alloc['domestic_filled']}/{alloc['domestic_demand']} (gap: {alloc['domestic_gap']})")

    if alloc["compliance_stockout"]:
        print(f"\n⚠️  COMPLIANCE STOCKOUT: {alloc['intl_gap']} international orders cannot be filled!")
    else:
        print(f"\n✅ No compliance stockout. Green fleet coverage: {alloc['fleet_green_pct']}%")

    print(f"\n⏰ Expiry Watch:")
    print(f"   Aging into Amber within 30 days: {alloc['assets_expiring_30d']}")
    print(f"   Aging into Amber within 90 days: {alloc['assets_expiring_90d']}")
    print(f"   Next expiry: {alloc['next_expiry_days']} days")
