"""
data_imputer.py
---------------
Two-phase imputation pipeline for FINAL_ CSV files.

Phase 1 (Original): Fill NaN/null values using stochastic methods
    - Poisson-distributed quantity fills
    - Median-grouped transit time fills with noise
    - Random manufacturing date generation for missing entries

Phase 2 (NEW): Historical Zero-Value Replacement
    - Any numeric field that is 0 or NaN is replaced with the best
      available historical average, using a 3-tier fallback:
        1. Customer-level mean for that metric
        2. Container-type mean across all customers
        3. Global column mean
    - The FINAL file should never have a zero if historical data exists.

Output:
    Overwrites FINAL_Documented_Loop_Times.csv,
               FINAL_MFG_Date.csv,
               FINAL_Receipt_to_Receipt_Data.csv,
               FINAL_Sales_QTY.csv  (in-place, same filenames always)
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import os
import re


# ── Shared helpers ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _path(filename: str) -> str:
    """Resolve a filename relative to this script's directory."""
    return os.path.join(BASE_DIR, filename)


def _find_col(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Return the first column whose name contains any of the keywords."""
    for col in df.columns:
        if any(k in col.lower() for k in keywords):
            return col
    return None


def _container_type(text) -> str:
    """Extract a canonical container type from a free-text field."""
    if not isinstance(text, str):
        return "Unknown"
    up = text.upper()
    if "55" in up and ("G" in up or "DRUM" in up):
        return "DR-55GAL"
    if "1000" in up and ("L" in up or "TOTE" in up):
        return "T-1000L"
    if "330" in up and ("G" in up or "TOTE" in up):
        return "T-330GAL"
    return "Unknown"


def _smart_fill_zeros(
    df: pd.DataFrame,
    numeric_cols: list[str],
    group_col: str | None,
    label: str,
) -> int:
    """
    Replace 0 and NaN in numeric_cols using 3-tier historical averages.

    Tier 1: Group-level mean (e.g., same customer or same container type)
    Tier 2: Global column mean
    Tier 3: Leave unchanged (only if entire column is 0/NaN)

    Returns the total number of values replaced.
    """
    total_replaced = 0

    for col in numeric_cols:
        mask = df[col].isin([0]) | df[col].isna()
        if not mask.any():
            continue

        count_before = mask.sum()

        # Tier 1: group-level mean (if a grouping column exists)
        if group_col and group_col in df.columns:
            group_means = df[~mask].groupby(group_col)[col].mean()
            df.loc[mask, col] = df.loc[mask, group_col].map(group_means)

        # Tier 2: global column mean for anything still 0/NaN
        still_bad = df[col].isin([0]) | df[col].isna()
        global_mean = df.loc[~mask, col].mean()
        if still_bad.any() and pd.notna(global_mean) and global_mean != 0:
            df.loc[still_bad, col] = round(global_mean, 1)

        # Count how many were actually replaced
        final_bad = df[col].isin([0]) | df[col].isna()
        replaced = count_before - final_bad.sum()
        if replaced > 0:
            total_replaced += replaced
            print(f"    {label} → {col}: replaced {replaced} zero/null values")

    return total_replaced


# ── Per-file imputers ─────────────────────────────────────────────────────────

def impute_loop_times() -> dict:
    """
    Impute FINAL_Documented_Loop_Times.csv.

    Phase 1: Fill NaN with container-type median + stochastic noise.
    Phase 2: Replace any remaining 0s with customer/container-type averages.
    """
    src = _path("CLEANED_Documented_Loop_Times.csv")
    dst = _path("FINAL_Documented_Loop_Times.csv")
    if not os.path.exists(src):
        print(f"  ⚠️ Skipping: {src} not found")
        return {"file": "Loop Times", "phase1": 0, "phase2": 0}

    df = pd.read_csv(src)

    # Identify the customer and container columns for grouping
    item_col = _find_col(df, ["item", "desc", "container", "product"])
    cust_col = _find_col(df, ["customer name", "customer"])

    if item_col:
        df["_container"] = df[item_col].apply(_container_type)
    else:
        df["_container"] = "Global"

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # ── Phase 1: Fill nulls with group median + noise ─────────────────────
    phase1_count = 0
    for col in num_cols:
        was_null = df[col].isna()
        nulls_before = was_null.sum()
        if nulls_before == 0:
            continue

        # Container-type median
        df[col] = df.groupby("_container")[col].transform(
            lambda x: x.fillna(x.median())
        )
        # Global fallback
        col_median = df[col].median()
        df[col] = df[col].fillna(col_median if pd.notna(col_median) else 0)

        # Stochastic noise for time-related fields (only on imputed rows)
        if any(k in col.lower() for k in ["transit", "time", "day", "loop"]):
            n_imputed = was_null.sum()
            noise = np.random.randint(-2, 3, size=n_imputed)
            df.loc[was_null, col] = (df.loc[was_null, col] + noise).clip(lower=0)

        phase1_count += nulls_before - df[col].isna().sum()

    # ── Phase 2: Replace zeros with historical averages ───────────────────
    # Use customer name as primary grouping, container type as fallback
    group = cust_col if cust_col else "_container"
    phase2_count = _smart_fill_zeros(df, num_cols, group, "Loop Times")

    df.drop(columns=["_container"], errors="ignore", inplace=True)
    df.to_csv(dst, index=False)
    return {"file": "Loop Times", "phase1": phase1_count, "phase2": phase2_count}


def impute_mfg_date() -> dict:
    """
    Impute FINAL_MFG_Date.csv.

    Replaces null or pre-2010 manufacturing dates with random dates
    between 2018-01-01 and 2023-12-31.
    """
    src = _path("CLEANED_MFG_Date.csv")
    dst = _path("FINAL_MFG_Date.csv")
    if not os.path.exists(src):
        print(f"  ⚠️ Skipping: {src} not found")
        return {"file": "MFG Date", "phase1": 0, "phase2": 0}

    df = pd.read_csv(src)
    date_col = _find_col(df, ["date", "mfg"])

    if not date_col:
        print("  ⚠️ MFG Date column not identified.")
        return {"file": "MFG Date", "phase1": 0, "phase2": 0}

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    mask = df[date_col].isna() | (df[date_col].dt.year < 2010)
    count = int(mask.sum())

    if count > 0:
        start_ts = pd.to_datetime("2018-01-01").value // 10**9
        end_ts = pd.to_datetime("2023-12-31").value // 10**9
        df.loc[mask, date_col] = pd.to_datetime(
            np.random.randint(start_ts, end_ts, size=count), unit="s"
        )

    df.to_csv(dst, index=False)
    return {"file": "MFG Date", "phase1": count, "phase2": 0}


def impute_r2r() -> dict:
    """
    Impute FINAL_Receipt_to_Receipt_Data.csv.

    Phase 1: Fill NaN R2R days with item-group mean; fill proportion cols.
    Phase 2: Replace remaining 0s with historical averages.
    """
    src = _path("CLEANED_Receipt_to_Receipt_Data.csv")
    dst = _path("FINAL_Receipt_to_Receipt_Data.csv")
    if not os.path.exists(src):
        print(f"  ⚠️ Skipping: {src} not found")
        return {"file": "R2R Data", "phase1": 0, "phase2": 0}

    df = pd.read_csv(src)

    item_col = _find_col(df, ["item", "desc", "product"])
    r2r_col = _find_col(df, ["r2r", "days", "median"])

    # ── Phase 1: Fill nulls ───────────────────────────────────────────────
    phase1_count = 0

    if r2r_col and df[r2r_col].isna().any():
        nulls_before = df[r2r_col].isna().sum()
        if item_col:
            df[r2r_col] = df.groupby(item_col)[r2r_col].transform(
                lambda x: x.fillna(x.mean())
            )
        df[r2r_col] = df[r2r_col].fillna(df[r2r_col].mean())
        phase1_count += nulls_before - df[r2r_col].isna().sum()

    # Fill proportional receipt columns
    total_col = _find_col(df, ["d365", "total", "serial"])
    zero_col = _find_col(df, ["0", "zero"])
    one_col = _find_col(df, ["1", "one"])

    if total_col and zero_col and one_col:
        m0 = df[zero_col].isna()
        if m0.any():
            df.loc[m0, zero_col] = np.floor(df.loc[m0, total_col].fillna(0) * 0.15)
            phase1_count += int(m0.sum())

        m1 = df[one_col].isna()
        if m1.any():
            df.loc[m1, one_col] = np.floor(df.loc[m1, total_col].fillna(0) * 0.25)
            phase1_count += int(m1.sum())

    # ── Phase 2: Replace zeros ────────────────────────────────────────────
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # Create a container-type grouping from the item column
    if item_col:
        df["_container"] = df[item_col].apply(_container_type)
        group = "_container"
    else:
        group = None

    phase2_count = _smart_fill_zeros(df, num_cols, group, "R2R Data")

    df.drop(columns=["_container"], errors="ignore", inplace=True)
    df.to_csv(dst, index=False)
    return {"file": "R2R Data", "phase1": phase1_count, "phase2": phase2_count}


def impute_sales() -> dict:
    """
    Impute FINAL_Sales_QTY.csv.

    Phase 1: Fill NaN quantities using Poisson distribution matched to
             customer/product group means.
    Phase 2: Replace 0-quantity rows with customer-level historical average.
    """
    src = _path("CLEANED_Sales_QTY.csv")
    dst = _path("FINAL_Sales_QTY.csv")
    if not os.path.exists(src):
        print(f"  ⚠️ Skipping: {src} not found")
        return {"file": "Sales QTY", "phase1": 0, "phase2": 0}

    df = pd.read_csv(src)

    cust_col = _find_col(df, ["customer", "client", "buyer"])
    qty_col = _find_col(df, ["qty", "quantity", "volume", "amount"])

    if not qty_col:
        print("  ⚠️ Sales QTY column not identified.")
        return {"file": "Sales QTY", "phase1": 0, "phase2": 0}

    # ── Phase 1: Fill nulls with Poisson imputation ───────────────────────
    phase1_count = int(df[qty_col].isna().sum())

    if phase1_count > 0:
        if cust_col:
            means = df.groupby(cust_col)[qty_col].transform("mean")
        else:
            means = pd.Series(df[qty_col].mean(), index=df.index)

        overall_mean = df[qty_col].mean()
        if pd.isna(overall_mean):
            overall_mean = 12.0
        means = means.fillna(overall_mean)

        mask = df[qty_col].isna()
        lambdas = np.maximum(means[mask].values, 0.001)
        df.loc[mask, qty_col] = np.random.poisson(lam=lambdas)

    # ── Phase 2: Replace zeros ────────────────────────────────────────────
    phase2_count = _smart_fill_zeros(df, [qty_col], cust_col, "Sales QTY")

    df.to_csv(dst, index=False)
    return {"file": "Sales QTY", "phase1": phase1_count, "phase2": phase2_count}


# ── Public entry point (called by data_cleaner.py) ────────────────────────────

def impute_all() -> list[dict]:
    """Run all imputers and return a list of result summaries."""
    return [
        impute_loop_times(),
        impute_mfg_date(),
        impute_r2r(),
        impute_sales(),
    ]


def print_summary(results: list[dict]) -> None:
    """Print a clean summary table of all imputation work."""
    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│           Imputation Summary                           │")
    print("├──────────────────────┬──────────┬───────────────────────┤")
    print("│ File                 │ Phase 1  │ Phase 2 (Zero-Fill)   │")
    print("├──────────────────────┼──────────┼───────────────────────┤")
    for r in results:
        name = r["file"].ljust(20)
        p1 = str(r["phase1"]).rjust(6)
        p2 = str(r["phase2"]).rjust(6)
        print(f"│ {name} │ {p1}   │ {p2}                  │")
    print("├──────────────────────┴──────────┴───────────────────────┤")

    total_p1 = sum(r["phase1"] for r in results)
    total_p2 = sum(r["phase2"] for r in results)
    print(f"│  Total: {total_p1} null-fills, {total_p2} zero-replacements".ljust(58) + "│")
    print("└─────────────────────────────────────────────────────────┘")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("─" * 58)
    print("  MLI Data Imputation Engine v2.0")
    print("  Phase 1: Null/NaN fill  │  Phase 2: Zero-value replacement")
    print("─" * 58)
    results = impute_all()
    print_summary(results)
    print("✅ All FINAL_ files updated in-place.")
