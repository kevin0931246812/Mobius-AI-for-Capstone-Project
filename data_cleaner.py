"""
data_cleaner.py
---------------
ETL (Extract, Transform, Load) pipeline for the MLI Capstone Dashboard.

This module reads raw data from the Excel workbook and produces two JSON
artefacts consumed by the simulation engine and dashboard:

  item_metrics.json      — Per-product demand, dwell, fleet size, and asset ages
  customer_insights.json — Per-customer order history, dwell, anomalies, and
                           contracted loop-time data for each product type
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import os
import json
import re
from data_imputer import impute_all, print_summary
from config import BASE_DIR, DATA_FILE_PATH


# ── Step 1: Sheet-level cleaning functions ────────────────────────────────────

def clean_sales_qty(file_path: str) -> pd.DataFrame:
    """
    Clean the 'Sales QTY' pivot sheet.

    The raw sheet interleaves Customer/Product header rows with date-level data
    rows. This function:
      - Removes the 'Grand Total' summary row.
      - Identifies true date rows vs. customer/product header rows.
      - Forward-fills the customer/product label into a dedicated column.
      - Returns only date-level rows with [Customer/Product, Date, Quantity].
    """
    print("Cleaning 'Sales QTY' sheet...")
    df = pd.read_excel(file_path, sheet_name='Sales QTY')

    # Remove grand total row
    df = df[~df['Row Labels'].astype(str).str.strip().str.lower().eq('grand total')].copy()

    # Parse dates; rows that fail to parse are customer/product headers
    df['Date'] = pd.to_datetime(df['Row Labels'], errors='coerce')

    # Forward-fill the customer/product label from header rows into date rows
    df['Customer/Product'] = np.where(df['Date'].isna(), df['Row Labels'], np.nan)
    df['Customer/Product'] = df['Customer/Product'].ffill()

    # Keep only rows that have a valid date
    df_clean = df.dropna(subset=['Date']).copy()
    df_clean = df_clean.rename(columns={'Sum of Total Invent Qty': 'Quantity'})

    return df_clean[['Customer/Product', 'Date', 'Quantity']].reset_index(drop=True)


def clean_mfg_date(file_path: str) -> pd.DataFrame:
    """
    Clean the 'MFG Date' sheet.

    Converts the MFG DATE column to proper datetime and nullifies the Excel
    epoch sentinel value (1899-12-31) that represents missing dates.
    """
    print("Cleaning 'MFG Date' sheet...")
    df = pd.read_excel(file_path, sheet_name='MFG Date')
    df['MFG DATE'] = pd.to_datetime(df['MFG DATE'], errors='coerce')

    # Nullify Excel's legacy epoch date, which signals a missing value
    df.loc[df['MFG DATE'] == pd.Timestamp('1899-12-31'), 'MFG DATE'] = np.nan
    return df


def clean_loop_times(file_path: str) -> pd.DataFrame:
    """
    Clean the 'Documented Loop Times' sheet.

    Strips whitespace from column names to prevent lookup mismatches.
    """
    print("Cleaning 'Documented Loop Times' sheet...")
    df = pd.read_excel(file_path, sheet_name='Documented Loop Times')
    df.columns = df.columns.astype(str).str.strip()
    return df


def clean_r2r_data(file_path: str) -> pd.DataFrame:
    """
    Clean the 'Receipt to Receipt Data' sheet.

    Fills missing R2R median values with the column mean so that downstream
    dwell-time calculations are not disrupted by NaN entries.
    """
    print("Cleaning 'Receipt to Receipt Data' sheet...")
    df = pd.read_excel(file_path, sheet_name='Receipt to Receipt Data')
    if 'R2R Days (median)' in df.columns:
        col_mean = df['R2R Days (median)'].mean()
        df['R2R Days (median)'] = df['R2R Days (median)'].fillna(col_mean)
    return df


# ── Step 2: Label parsing helpers ─────────────────────────────────────────────

def parse_item_type(label: str) -> str:
    """
    Map a raw Customer/Product label to one of the three canonical item types.

    Returns 'Other' for labels that don't match any known product.
    """
    label_upper = str(label).upper()
    if '1000L' in label_upper: return '1000L Tote'
    if '55GAL' in label_upper: return '55GAL Drum'
    if '330GAL' in label_upper: return '330GAL Tote'
    return 'Other'


def parse_customer_name(label: str) -> str:
    """
    Extract a clean customer name from a raw Sales Customer/Product label.

    Tries multiple regex patterns before falling back to splitting on '('.
    """
    label = str(label).strip()

    # Pattern 1: "Customer ABC" style labels
    m = re.match(r'^(Customer\s+\w+)', label, re.IGNORECASE)
    if m:
        return m.group(1).title()

    # Pattern 2: alphanumeric name ending before a digit or parenthesis
    m = re.match(r'^([A-Za-z0-9\s\-]+?)(?:\s+\d|\s+\()', label)
    if m:
        return m.group(1).strip().title()

    # Fallback: everything before the first '('
    return label.split('(')[0].strip()


def parse_r2r_customer_name(label: str) -> str | None:
    """
    Extract a customer name from an R2R Item string.

    Returns None if no customer pattern is found.
    """
    matches = re.findall(r'Customer[\s\-]?\w+', str(label), re.IGNORECASE)
    if matches:
        return matches[-1].replace('-', ' ').title().strip()
    return None


# ── Step 3: Metric generation ─────────────────────────────────────────────────

def generate_item_metrics(
    df_sales: pd.DataFrame,
    df_mfg:   pd.DataFrame,
    df_r2r:   pd.DataFrame,
    target_dir: str
) -> None:
    """
    Derive per-product simulation inputs and write them to item_metrics.json.

    For each product type (1000L Tote, 55GAL Drum, 330GAL Tote) this computes:
      - daily_demand : average units shipped per calendar day
      - dwell_mean   : median R2R return time (days)
      - fleet_size   : count of assets with known manufacturing dates
      - ages          : list of individual asset ages in days (from MFG dates)
    """
    print("Generating item-specific metrics...")

    # Tag each row with its canonical item type
    df_sales['Item Type'] = df_sales['Customer/Product'].apply(parse_item_type)
    df_mfg['Item Type']   = df_mfg['FG part number'].apply(parse_item_type)
    df_r2r['Item Type']   = df_r2r['Item'].apply(parse_item_type)

    df_sales['Date'] = pd.to_datetime(df_sales['Date'])

    results = {}
    for item in df_sales['Item Type'].unique():
        if item == 'Other':
            continue

        # Daily demand: total quantity divided by the full date span
        item_sales = df_sales[df_sales['Item Type'] == item]
        date_span  = (item_sales['Date'].max() - item_sales['Date'].min()).days
        daily_demand = round(item_sales['Quantity'].sum() / date_span, 2) if date_span > 0 else 100

        # Dwell mean: average of R2R median return times for this item
        item_r2r   = df_r2r[df_r2r['Item Type'] == item]
        dwell_mean = int(item_r2r['R2R Days (median)'].median()) if not item_r2r.empty else 10

        # Asset ages: derived from manufacturing dates vs. today
        item_mfg = df_mfg[df_mfg['Item Type'] == item]
        if not item_mfg.empty:
            today  = pd.Timestamp.today()
            ages   = (today - item_mfg['MFG DATE']).dt.days.dropna().astype(int).tolist()
        else:
            ages = []

        fleet_size = len(ages) if ages else 100

        results[item] = {
            'daily_demand': daily_demand,
            'dwell_mean':   dwell_mean,
            'fleet_size':   fleet_size,
            'ages':         ages
        }

    output_path = os.path.join(target_dir, 'item_metrics.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=4)
    print("Created item_metrics.json")


# ── Step 4: Customer insight generation ───────────────────────────────────────

def generate_customer_insights(
    df_sales: pd.DataFrame,
    df_r2r:   pd.DataFrame,
    df_loop:  pd.DataFrame,
    target_dir: str
) -> None:
    """
    Build per-customer enriched profiles and write them to customer_insights.json.

    For each product × customer combination this computes:
      - Ordering frequency and volume statistics
      - Actual dwell time (from R2R data)
      - Variance versus the top-tier benchmark dwell
      - Complete monthly order history
      - Statistical anomalies (Z-score > 2.0 demand spikes)
      - Contracted loop-time assumptions (from 'Documented Loop Times' sheet)
    """
    print("Generating customer insights...")

    # ── Prepare sales data ───────────────────────────────────────────────────
    df_sales = df_sales.copy()
    df_sales['Date']      = pd.to_datetime(df_sales['Date'])
    df_sales['Item']      = df_sales['Customer/Product'].apply(parse_item_type)
    df_sales['Customer']  = df_sales['Customer/Product'].apply(parse_customer_name)
    df_sales['CustKey']   = df_sales['Customer/Product'].apply(parse_r2r_customer_name)
    df_sales['MatchKey']  = df_sales['CustKey'].astype(str).str.lower().str.replace(r'\s+', '', regex=True)
    df_sales['YearMonth'] = df_sales['Date'].dt.to_period('M').astype(str)

    # ── Prepare R2R data with normalised match keys ──────────────────────────
    df_r2r = df_r2r.copy()
    df_r2r['ItemType'] = df_r2r['Item'].apply(parse_item_type)
    df_r2r['CustKey']  = df_r2r['Item'].apply(parse_r2r_customer_name)
    df_r2r['MatchKey'] = df_r2r['CustKey'].astype(str).str.lower().str.replace(r'\s+', '', regex=True)

    # ── Prepare documented loop data with normalised match keys ─────────────
    df_loop = df_loop.copy()
    df_loop['ItemType'] = df_loop['Returnable Container P/N'].apply(parse_item_type)
    df_loop['CustKey']  = df_loop['Customer Name'].apply(parse_r2r_customer_name)
    df_loop['MatchKey'] = df_loop['CustKey'].astype(str).str.lower().str.replace(r'\s+', '', regex=True)

    def safe_float(value) -> float | str:
        """Safely convert a value to a rounded float, returning 'N/A' if invalid."""
        try:
            return round(float(value), 1) if pd.notna(value) else 'N/A'
        except (TypeError, ValueError):
            return 'N/A'

    insights = {}
    for item in ['1000L Tote', '55GAL Drum', '330GAL Tote']:
        item_sales = df_sales[df_sales['Item'] == item]
        if item_sales.empty:
            insights[item] = []
            continue

        # Date range helpers for normalising volumes to annual/monthly rates
        date_range_months = max(1, (item_sales['Date'].max() - item_sales['Date'].min()).days / 30.0)
        date_range_days   = max(1, (item_sales['Date'].max() - item_sales['Date'].min()).days)
        total_active_months = item_sales['YearMonth'].nunique()

        # ── Benchmark dwell: average of the fastest 20% of customers (R2R) ──
        item_r2r  = df_r2r[df_r2r['ItemType'] == item].copy()
        dwell_vals = item_r2r['R2R Days (median)'].dropna()

        if len(dwell_vals) >= 2:
            top_tier_cutoff   = dwell_vals.quantile(0.20)
            benchmark_dwell   = round(dwell_vals[dwell_vals <= top_tier_cutoff].mean(), 1)
        else:
            benchmark_dwell   = round(dwell_vals.mean(), 1) if not dwell_vals.empty else 0

        # Per-customer dwell lookup from R2R (keyed by normalised customer name)
        customer_dwell_map = item_r2r.groupby('MatchKey')['R2R Days (median)'].mean().to_dict()

        item_loop = df_loop[df_loop['ItemType'] == item].copy()

        # Process customers in descending order of total volume
        customer_volumes = item_sales.groupby('Customer')['Quantity'].sum().sort_values(ascending=False)
        rows = []

        for customer_name in customer_volumes.index:
            cust_sales = item_sales[item_sales['Customer'] == customer_name]
            
            # Extract precise raw match key to link directly to R2R and Loop mappings
            match_key = cust_sales['MatchKey'].iloc[0]

            # ── Volume statistics ────────────────────────────────────────────
            total_qty   = int(cust_sales['Quantity'].sum())
            annual_qty  = round(total_qty / date_range_days * 365, 1)
            avg_monthly = round(total_qty / date_range_months, 1)

            # ── Ordering frequency label ────────────────────────────────────
            active_months = int(cust_sales['YearMonth'].nunique())
            freq_ratio    = active_months / max(total_active_months, 1)
            
            if   freq_ratio >= 0.80: freq_label = 'Consistent'
            elif freq_ratio >= 0.50: freq_label = 'Regular'
            elif freq_ratio >= 0.25: freq_label = 'Seasonal'
            else:                    freq_label = 'Sporadic'

            # ── Actual dwell time and benchmark variance ─────────────────────
            actual_dwell = customer_dwell_map.get(match_key)
            dwell_source = "actual"
            if actual_dwell is None and not dwell_vals.empty:
                # Fallback: product-type median R2R as best estimate
                actual_dwell = float(dwell_vals.median())
                dwell_source = "estimated"

            if actual_dwell is not None and benchmark_dwell > 0:
                dwell_variance = round(actual_dwell - benchmark_dwell, 1)
            else:
                dwell_variance = 'N/A'

            # ── Monthly order history ────────────────────────────────────────
            raw_history  = cust_sales[['Date', 'Quantity']].sort_values('Date')
            history_list = [
                {'date': d.strftime('%Y-%m-%d'), 'qty': int(q)}
                for d, q in zip(raw_history['Date'], raw_history['Quantity'])
            ]

            # ── Buying Pattern & Avg Order Qty ───────────────────────────────
            if len(raw_history) > 1:
                date_diffs = raw_history['Date'].diff().dt.days.dropna()
                avg_days = date_diffs.mean()
                if avg_days <= 10:
                    buying_pattern = 'Weekly'
                elif avg_days <= 24:
                    buying_pattern = 'Bi-Weekly'
                elif avg_days <= 45:
                    buying_pattern = 'Monthly'
                else:
                    buying_pattern = 'Random'
            else:
                avg_days = 'N/A'
                buying_pattern = 'Random'
                
            avg_order_qty = round(raw_history['Quantity'].mean(), 1) if not raw_history.empty else 0

            # ── Anomaly detection (Z-score > 2.0 = unusual demand spike) ────
            anomalies = []
            if len(raw_history) >= 3:
                mean_qty = raw_history['Quantity'].mean()
                std_qty  = raw_history['Quantity'].std()
                if std_qty > 0:
                    for date, qty in zip(raw_history['Date'], raw_history['Quantity']):
                        z_score = (qty - mean_qty) / std_qty
                        if z_score > 2.0:
                            anomalies.append({
                                'date':    date.strftime('%Y-%m-%d'),
                                'qty':     int(qty),
                                'z_score': round(z_score, 2)
                            })

            # ── Contracted loop-time data (from 'Documented Loop Times') ────
            cust_loop = item_loop[item_loop['MatchKey'] == match_key]
            if not cust_loop.empty:
                loop_row = cust_loop.iloc[0]
                doc_total_time        = loop_row.get('Total Transit Time (Days)',                         'N/A')
                doc_consignment_max   = loop_row.get('Consignment Max',                                   'N/A')
                doc_daily_consumption = loop_row.get('Daily Consumption',                                 'N/A')
                doc_transit_out       = loop_row.get('Transit Time to Customer Site (Days)',               'N/A')
                doc_transit_in        = loop_row.get('Transit Time to MLI (Days)',                        'N/A')
                doc_touch_points      = loop_row.get('Any other touch points? (empties at warehouse) (Days)', 'N/A')
            else:
                doc_total_time = doc_consignment_max = doc_daily_consumption = 'N/A'
                doc_transit_out = doc_transit_in = doc_touch_points = 'N/A'

            rows.append({
                'customer':              customer_name,
                'avg_monthly_units':     avg_monthly,
                'annual_qty':            annual_qty,
                'frequency_label':       freq_label,
                'buying_pattern':        buying_pattern,
                'avg_order_qty':         avg_order_qty,
                'active_months':         active_months,
                'total_months':          int(total_active_months),
                'late_variance':         dwell_variance,
                'avg_dwell_time':        round(actual_dwell, 1) if actual_dwell is not None else 'N/A',
                'dwell_source':          dwell_source,
                'history':               history_list,
                'anomalies':             anomalies,
                'doc_total_time':        safe_float(doc_total_time),
                'doc_consignment_max':   safe_float(doc_consignment_max),
                'doc_daily_consumption': safe_float(doc_daily_consumption),
                'doc_transit_out':       safe_float(doc_transit_out),
                'doc_transit_in':        safe_float(doc_transit_in),
                'doc_touch_points':      safe_float(doc_touch_points),
            })

        insights[item] = rows

    output_path = os.path.join(target_dir, 'customer_insights.json')
    with open(output_path, 'w') as f:
        json.dump(insights, f, indent=4)
    print("Created customer_insights.json")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    """
    Run the full ETL pipeline:
      1. Read and clean all four Excel sheets.
      2. Save individual cleaned CSVs for audit/debugging.
      3. Generate item_metrics.json for the simulation engine.
      4. Generate customer_insights.json for the dashboard customer view.
    """
    file_path  = DATA_FILE_PATH
    target_dir = BASE_DIR

    if not os.path.exists(file_path):
        print(f"Error: Data file not found at {file_path}")
        return

    # ── Clean each sheet ─────────────────────────────────────────────────────
    df_sales = clean_sales_qty(file_path)
    df_sales.to_csv(os.path.join(target_dir, "CLEANED_Sales_QTY.csv"), index=False)

    df_mfg = clean_mfg_date(file_path)
    df_mfg.to_csv(os.path.join(target_dir, "CLEANED_MFG_Date.csv"), index=False)

    df_loop = clean_loop_times(file_path)
    df_loop.to_csv(os.path.join(target_dir, "CLEANED_Documented_Loop_Times.csv"), index=False)

    df_r2r = clean_r2r_data(file_path)
    df_r2r.to_csv(os.path.join(target_dir, "CLEANED_Receipt_to_Receipt_Data.csv"), index=False)
    
    # ── Run imputation (Phase 1: null-fill + Phase 2: zero-replacement) ────
    print("Running imputation engine on CLEANED → FINAL files...")
    results = impute_all()
    print_summary(results)
    
    # Reload the fully populated FINAL CSVs so they don't break string/date types
    print("Reloading FULLY IMPUTED data into AI memory pipeline...")
    df_sales_final = pd.read_csv(os.path.join(target_dir, "FINAL_Sales_QTY.csv"), parse_dates=['Date'])
    df_mfg_final = pd.read_csv(os.path.join(target_dir, "FINAL_MFG_Date.csv"), parse_dates=['MFG DATE'])
    df_loop_final = pd.read_csv(os.path.join(target_dir, "FINAL_Documented_Loop_Times.csv"))
    df_r2r_final = pd.read_csv(os.path.join(target_dir, "FINAL_Receipt_to_Receipt_Data.csv"))

    # ── Sync MFG data — generate containers for products in Sales but missing from MFG
    from mfg_generator import sync_mfg_data
    df_mfg_combined = sync_mfg_data(
        sales_path=os.path.join(target_dir, "FINAL_Sales_QTY.csv"),
        mfg_path=os.path.join(target_dir, "FINAL_MFG_Date.csv"),
    )

    # ── Generate JSON artefacts using FILLED data + combined MFG ───────────────
    generate_item_metrics(df_sales_final, df_mfg_combined, df_r2r_final, target_dir)
    generate_customer_insights(df_sales_final, df_r2r_final, df_loop_final, target_dir)

    print("Data cleaning completed successfully.")


if __name__ == "__main__":
    main()
