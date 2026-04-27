"""
live_twin_engine.py
-------------------
A daily simulation engine for the MLI Digital Twin. 
Generates virtual daily data based on historical trends (buying_pattern and avg_order_qty).
This script operates independently of fleet_sim.py and acts as the backend for the 
"Real World Simulation" desk in the Interactive Office Hub.
"""
from __future__ import annotations
import json
import numpy as np
import random
from datetime import datetime

from config import CUSTOMER_INSIGHTS_PATH

def get_order_probability(pattern: str) -> float:
    """Return the daily probability of an order based on the buying pattern."""
    if pattern == 'Weekly': return 1.0 / 7.0
    if pattern == 'Bi-Weekly': return 1.0 / 14.0
    if pattern == 'Monthly': return 1.0 / 30.0
    return 1.0 / 60.0  # Random or Sporadic

def generate_today(current_date: str | datetime, product_type: str = "55GAL Drum") -> dict:
    """
    Simulate a single day of activity in the live digital twin.
    
    Args:
        current_date: The current date being simulated (string or datetime).
        product_type: The product to simulate for (default "55GAL Drum").
        
    Returns:
        dict: A summary of today's total simulated statistics.
    """
    if isinstance(current_date, str):
        try:
            current_date = datetime.strptime(current_date, "%Y-%m-%d")
        except ValueError:
            current_date = datetime.now()
            
    # Deterministic seed based on date so the "Live Twin" is completely reproducible 
    # if queried for the same historical day.
    seed = int(current_date.strftime("%Y%m%d"))
    rng = np.random.default_rng(seed)
    rng_stdlib = random.Random(seed)

    try:
        with open(CUSTOMER_INSIGHTS_PATH, 'r') as f:
            insights = json.load(f)
    except Exception as e:
        print(f"Error loading {CUSTOMER_INSIGHTS_PATH}: {e}")
        return {}

    customers = insights.get(product_type, [])
    
    daily_stats = {
        "date": current_date.strftime("%Y-%m-%d"),
        "total_orders_placed": 0,
        "total_units_shipped": 0,
        "total_empties_returned": 0,
        "total_anomalies": 0,
        "delayed_units": 0,
        "events": []
    }
    
    for customer in customers:
        name = customer.get("customer", "Unknown")
        pattern = customer.get("buying_pattern", "Random")
        avg_qty = customer.get("avg_order_qty", 0)
        
        # Skip customers with zero historical volume
        if avg_qty <= 0:
            continue
            
        prob_order = get_order_probability(pattern)
        
        # ── 1. Simulate Orders Placed Today ──
        if rng_stdlib.random() < prob_order:
            order_volume = rng.poisson(lam=avg_qty)
            if order_volume > 0:
                daily_stats["total_orders_placed"] += 1
                daily_stats["total_units_shipped"] += order_volume
                daily_stats["events"].append({
                    "customer": name,
                    "type": "New Order Shipped",
                    "volume": int(order_volume)
                })
                
        # ── 2. Simulate Empties Returning Today ──
        # Assume empties return in batches similar to order frequencies but perhaps less predictably
        prob_return = get_order_probability(pattern) * 0.85
        if rng_stdlib.random() < prob_return:
            return_volume = rng.poisson(lam=avg_qty)
            if return_volume > 0:
                daily_stats["total_empties_returned"] += return_volume
                daily_stats["events"].append({
                    "customer": name,
                    "type": "Empties Returned",
                    "volume": int(return_volume)
                })
                
    # ── 3. Simulate Anomalies ──
    # Global 10% chance for an anomaly to occur somewhere in the network today.
    # An anomaly delays 2 to 5 drums targeting a random customer.
    if customers and rng_stdlib.random() < 0.10:
        delayed_qty = rng_stdlib.randint(2, 5)
        affected_customer = rng_stdlib.choice(customers).get("customer", "Unknown")
        
        daily_stats["total_anomalies"] += 1
        daily_stats["delayed_units"] += delayed_qty
        daily_stats["events"].append({
            "customer": affected_customer,
            "type": "Transit Anomaly",
            "volume": delayed_qty,
            "issue": f"{delayed_qty} units delayed in transit."
        })
            
    return daily_stats

if __name__ == "__main__":
    # Run a quick test locally
    today_str = datetime.now().strftime("%Y-%m-%d")
    results = generate_today(today_str, "55GAL Drum")
    print(f"--- Live Twin Engine Results for {today_str} ---")
    print(json.dumps(results, indent=2))
