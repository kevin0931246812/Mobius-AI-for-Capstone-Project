"""
config.py
---------
Central configuration — all paths derived from one BASE_DIR.
Eliminates hardcoded absolute paths across the project.
"""

import os

# ── Base directory (root of the project) ──────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Source data ───────────────────────────────────────────────────────────────
DATA_FILE_PATH = os.path.join(BASE_DIR, "MLI Capstone Data.xlsx")
VIDEO_PATH     = os.path.join(BASE_DIR, "background.mp4")

# ── FINAL CSV files ───────────────────────────────────────────────────────────
FINAL_SALES_PATH = os.path.join(BASE_DIR, "FINAL_Sales_QTY.csv")
FINAL_MFG_PATH   = os.path.join(BASE_DIR, "FINAL_MFG_Date.csv")
FINAL_LOOP_PATH  = os.path.join(BASE_DIR, "FINAL_Documented_Loop_Times.csv")
FINAL_R2R_PATH   = os.path.join(BASE_DIR, "FINAL_Receipt_to_Receipt_Data.csv")

# ── JSON artifacts ────────────────────────────────────────────────────────────
ITEM_METRICS_PATH      = os.path.join(BASE_DIR, "item_metrics.json")
CUSTOMER_INSIGHTS_PATH = os.path.join(BASE_DIR, "customer_insights.json")
ANOMALY_ARCHIVE_PATH   = os.path.join(BASE_DIR, "anomaly_archive.json")

# ── Asset files ───────────────────────────────────────────────────────────────
GIF_PATH         = os.path.join(BASE_DIR, "Mobious.gif")
LOGO_PATH        = os.path.join(BASE_DIR, "mobius_logo.png")
FOOTER_LOGO_PATH = os.path.join(BASE_DIR, "footer_logos.png")

# ── Excel sheet names ─────────────────────────────────────────────────────────
SHEET_CONTRACTS = "Documented Loop Times"
SHEET_R2R       = "Receipt to Receipt Data"
