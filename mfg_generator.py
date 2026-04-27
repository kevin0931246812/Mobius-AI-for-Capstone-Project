"""
MFG Data Generator — Auto-creates realistic manufacturing records for containers
that exist in Sales but have no MFG tracking data.

This module is "alive": every time the app runs, it scans FINAL_Sales_QTY.csv for
customer/product combinations that don't yet exist in FINAL_MFG_Date.csv, then
generates logically consistent MFG records (serial numbers, dates, part numbers).

Key logic:
  - Number of containers = ceil(peak_monthly_volume / avg_trips_per_container)
  - MFG dates are spread over a realistic window based on item type lifespan
  - Serial numbers follow the MLI-{prefix}-{number} convention
  - Green/Amber age distribution mimics the real 1000L fleet profile
"""

import pandas as pd
import numpy as np
from pathlib import Path
import hashlib

# ── Configuration ──────────────────────────────────────────────────────────────
CONTAINER_PROFILES = {
    "55GAL": {
        "prefix": "DR",                  # Serial prefix: MLI-DR-XXXX
        "item_template": "DR-55GAL-TMAH {pct}-{suffix}",
        "fg_template": "{cust_clean} ({item})",
        "avg_lifespan_years": 5,          # Typical drum lifespan
        "trips_per_year": 6,              # Drums cycle faster (smaller)
        "fleet_ratio": 0.35,              # Need 35% of annual volume as fleet
    },
    "330GAL": {
        "prefix": "TT",                  # Serial prefix: MLI-TT-XXXX
        "item_template": "TT-330GAL-TMAH {pct}-{suffix}",
        "fg_template": "{cust_clean} ({item})",
        "avg_lifespan_years": 6,
        "trips_per_year": 4,
        "fleet_ratio": 0.5,
    },
    "Other": {
        "prefix": "OT",                  # Serial prefix: MLI-OT-XXXX
        "item_template": "OT-MISC-{suffix}",
        "fg_template": "{cust_clean} ({item})",
        "avg_lifespan_years": 4,
        "trips_per_year": 5,
        "fleet_ratio": 0.4,
    },
}


def _classify_product(label: str) -> str:
    """Classify a Customer/Product label into a container type."""
    u = str(label).upper()
    if "1000L" in u:
        return "1000L"
    if "55GAL" in u:
        return "55GAL"
    if "330GAL" in u:
        return "330GAL"
    return "Other"


def _extract_pct(label: str) -> str:
    """Extract percentage from label like 'Customer AC 25%' → '25%'."""
    import re
    m = re.search(r'(\d+\.?\d*%)', label)
    return m.group(1) if m else ""


def _customer_suffix(cust_name: str) -> str:
    """Generate a short, deterministic suffix from customer name."""
    # e.g., "Customer AC 25%" → "AC"
    parts = cust_name.replace("%", "").split()
    if len(parts) >= 2 and parts[0].lower() == "customer":
        return parts[1].upper()
    # Fallback: hash-based 3-char suffix
    return hashlib.md5(cust_name.encode()).hexdigest()[:3].upper()


def _generate_mfg_dates(n: int, profile: dict, rng: np.random.Generator) -> pd.Series:
    """
    Generate realistic MFG dates spread over the container lifespan.
    Mimics the real fleet's age distribution:
      - ~60% manufactured in the last 3 years (Green)
      - ~40% older than 4.25 years (Amber)
    """
    now = pd.Timestamp.now()
    max_age_days = int(profile["avg_lifespan_years"] * 365)

    # Create a bimodal distribution: recent + aged
    n_recent = int(n * 0.6)
    n_aged = n - n_recent

    # Recent: 0–1200 days ago (Green zone, < 4.25 years)
    recent_days = rng.integers(30, min(1200, max_age_days), size=n_recent)

    # Aged: 1551–max_age_days (Amber zone, > 4.25 years)
    aged_lower = 1551
    aged_upper = max(aged_lower + 100, max_age_days)
    aged_days = rng.integers(aged_lower, aged_upper, size=n_aged)

    all_days = np.concatenate([recent_days, aged_days])
    rng.shuffle(all_days)

    dates = [now - pd.Timedelta(days=int(d)) for d in all_days]
    return pd.Series(dates)


def _next_serial_start(existing_mfg: pd.DataFrame) -> int:
    """Find the next available serial number after existing ones."""
    import re
    max_num = 7000  # Start after existing MLI-XXXX range
    for s in existing_mfg["Serial number"]:
        nums = re.findall(r'\d+', str(s))
        if nums:
            max_num = max(max_num, max(int(n) for n in nums))
    return max_num + 1


def generate_missing_mfg(
    sales_path: str = "FINAL_Sales_QTY.csv",
    mfg_path: str = "FINAL_MFG_Date.csv",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Scan Sales data for customer/product combos that lack MFG records.
    Generate realistic container fleet data for those missing entries.

    Returns: DataFrame with new MFG records (same schema as existing MFG data).
    """
    base = Path(sales_path).parent
    sales = pd.read_csv(sales_path, parse_dates=["Date"])
    mfg = pd.read_csv(mfg_path, parse_dates=["MFG DATE"])

    rng = np.random.default_rng(seed)

    # Classify all sales entries
    sales["_type"] = sales["Customer/Product"].apply(_classify_product)
    sales["_cust"] = sales["Customer/Product"].str.split("(").str[0].str.strip()

    # 1000L already has MFG data — only generate for missing types
    types_needing_gen = ["55GAL", "330GAL", "Other"]
    missing = sales[sales["_type"].isin(types_needing_gen)]

    if missing.empty:
        return pd.DataFrame(columns=mfg.columns)

    # Group by customer × type to determine fleet size
    groups = (
        missing.groupby(["_cust", "_type"])
        .agg(
            total_qty=("Quantity", "sum"),
            n_months=("Date", lambda x: max(1, (x.max() - x.min()).days / 30)),
            first_ship=("Date", "min"),
        )
        .reset_index()
    )

    serial_counter = _next_serial_start(mfg)
    new_records = []

    for _, grp in groups.iterrows():
        cust = grp["_cust"]
        ptype = grp["_type"]
        total_qty = grp["total_qty"]
        n_months = grp["n_months"]

        profile = CONTAINER_PROFILES.get(ptype, CONTAINER_PROFILES["Other"])

        # Calculate fleet size: based on monthly throughput and cycle rate
        monthly_avg = total_qty / max(n_months, 1)
        trips_per_month = profile["trips_per_year"] / 12
        fleet_size = max(3, int(np.ceil(monthly_avg * profile["fleet_ratio"] / max(trips_per_month, 0.5))))

        # Cap at reasonable size to avoid generating huge datasets
        fleet_size = min(fleet_size, 200)

        # Build item number and FG part number
        pct = _extract_pct(cust)
        suffix = _customer_suffix(cust)
        item_num = profile["item_template"].format(pct=pct, suffix=suffix)
        fg_part = profile["fg_template"].format(cust_clean=cust, item=item_num)

        # Generate serial numbers
        serials = [f"MLI-{profile['prefix']}-{serial_counter + i:04d}" for i in range(fleet_size)]
        serial_counter += fleet_size

        # Generate MFG dates
        mfg_dates = _generate_mfg_dates(fleet_size, profile, rng)

        # Build records
        for serial, mfg_date in zip(serials, mfg_dates):
            new_records.append({
                "Customer": cust,
                "FG part number": fg_part,
                "Item number": item_num,
                "Serial number": serial,
                "MFG DATE": mfg_date,
            })

    new_df = pd.DataFrame(new_records)
    return new_df


def sync_mfg_data(
    sales_path: str = "FINAL_Sales_QTY.csv",
    mfg_path: str = "FINAL_MFG_Date.csv",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Main entry point: merge existing MFG data with auto-generated records
    for any customer/products found in Sales but missing from MFG.

    This function is idempotent — it checks for existing customers before
    adding new ones, so it's safe to call on every app startup.

    Returns: Complete MFG DataFrame (existing + newly generated).
    """
    mfg = pd.read_csv(mfg_path, parse_dates=["MFG DATE"])

    # Clamp any future MFG dates to today (fixes the 4 anomalous 2026-08-01 records)
    mfg["MFG DATE"] = mfg["MFG DATE"].clip(upper=pd.Timestamp.now())

    new_records = generate_missing_mfg(sales_path, mfg_path, seed)

    if new_records.empty:
        print("  ✅ MFG sync: all customers already have container records")
        return mfg

    # Check which customers already exist to avoid duplicates
    existing_custs = set(mfg["Customer"].unique())
    truly_new = new_records[~new_records["Customer"].isin(existing_custs)]

    if truly_new.empty:
        print("  ✅ MFG sync: all customers already have container records")
        return mfg

    combined = pd.concat([mfg, truly_new], ignore_index=True)

    # Report what was generated
    new_custs = truly_new["Customer"].nunique()
    new_containers = len(truly_new)
    print(f"  🏭 MFG sync: generated {new_containers} containers for {new_custs} new customers")
    for cust in sorted(truly_new["Customer"].unique()):
        n = (truly_new["Customer"] == cust).sum()
        item = truly_new[truly_new["Customer"] == cust]["Item number"].iloc[0]
        print(f"    + {cust}: {n} containers ({item})")

    return combined


# ── CLI test ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    sales_path = sys.argv[1] if len(sys.argv) > 1 else "FINAL_Sales_QTY.csv"
    mfg_path = sys.argv[2] if len(sys.argv) > 2 else "FINAL_MFG_Date.csv"

    print("🏭 MFG Data Generator — Scanning for missing containers...\n")
    result = sync_mfg_data(sales_path, mfg_path)
    print(f"\n📊 Final fleet: {len(result)} total containers")
    print(f"   By customer:")
    for cust in sorted(result["Customer"].unique()):
        n = (result["Customer"] == cust).sum()
        print(f"     {cust}: {n}")
    print(f"\n   By type:")
    for item in sorted(result["Item number"].unique()):
        n = (result["Item number"] == item).sum()
        print(f"     {item}: {n}")
