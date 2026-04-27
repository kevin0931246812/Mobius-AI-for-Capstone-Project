"""
fleet_sim.py
------------
Monte Carlo fleet simulation engine for the MLI Capstone Dashboard.

This module:
  - Loads real-world item metrics (demand, dwell, fleet size, asset ages)
    that were produced by data_cleaner.py.
  - Runs a discrete-event simulation of asset lifecycle states:
      Warehouse → TransitOut → Customer → TransitIn → Maintenance → Warehouse
  - Uses binary search to find the *minimum* fleet size that achieves a given
    service-level (target availability).
  - Returns the optimal fleet size and a Plotly figure for display in app.py.
"""

import random
import math
import plotly.graph_objects as go
import pandas as pd
import os
import json

# ── File paths ────────────────────────────────────────────────────────────────
from config import ITEM_METRICS_PATH as METRICS_PATH

# ── Simulation constants ──────────────────────────────────────────────────────
# These represent real-world operational parameters. Do not change without
# updating the underlying business assumptions.
SIMULATION_DAYS        = 365          # Number of days in the main simulation run
WARMUP_DAYS            = 100          # Warm-up period to reach steady state (excluded from metrics)
EU_MAX_AGE_DAYS        = int(4.25 * 365)  # 1,551 days — EU regulatory asset lifetime limit

# Transit time ranges (days), sampled uniformly each trip
TRANSIT_OUT_MIN, TRANSIT_OUT_MAX = 2, 5   # MLI → Customer
TRANSIT_IN_MIN,  TRANSIT_IN_MAX  = 2, 5   # Customer → MLI
MAINTENANCE_MIN, MAINTENANCE_MAX = 1, 3   # Inspection/cleaning at MLI

# Dwell time variability (standard deviation, in days)
CUSTOMER_DWELL_STD_DEV = 3

# Loss rate per trip (applies when an asset leaves the customer site)
ASSET_LOSS_RATE = 0.003   # 0.3% chance of loss per completed customer trip


# ── Data loading helpers ──────────────────────────────────────────────────────

def load_item_metrics() -> dict:
    """Load the item-level metrics JSON produced by data_cleaner.py."""
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH, "r") as f:
            return json.load(f)
    return {}


def get_item_names() -> list:
    """Return the list of product names available in item_metrics.json."""
    return list(load_item_metrics().keys())


def get_item_defaults(item_name: str) -> tuple:
    """
    Return (daily_demand, dwell_mean, fleet_size, age_list) for a given item.
    Falls back to sensible defaults if the item is not found.
    """
    metrics = load_item_metrics()
    if item_name in metrics:
        m = metrics[item_name]
        return (
            m.get("daily_demand", 100),
            m.get("dwell_mean", 10),
            m.get("fleet_size", 200),
            m.get("ages", [])
        )
    return 100, 10, 200, []


# ── Asset class ───────────────────────────────────────────────────────────────

class Asset:
    """
    Represents a single returnable asset (drum, tote, etc.) in the supply chain.

    States:
        Warehouse   → available at MLI for shipment
        TransitOut  → en route to customer
        Customer    → sitting at customer site (dwell period)
        TransitIn   → en route back to MLI
        Maintenance → inspection/cleaning at MLI before being returned to stock
    """

    def __init__(self, age_days: int = 0, eu_exposure_percent: float = 0.20, eu_max_age_days: int = 1551):
        self.age_days               = age_days
        self.state                  = "Warehouse"
        self.days_in_current_state  = 0
        self.target_state_duration  = 0   # How many days the asset stays in its current state
        self.active                 = True
        self.eu_max_age_days        = eu_max_age_days
        # Randomly assign EU exposure at "birth" based on the configured percentage
        self.is_eu_asset            = random.random() < eu_exposure_percent

    def tick(self):
        """Advance the asset by one day; retire EU-flagged assets past their age limit."""
        if not self.active:
            return
        self.age_days += 1
        self.days_in_current_state += 1
        # EU regulation: assets over the maximum age must be decommissioned
        if self.is_eu_asset and self.age_days > self.eu_max_age_days:
            self.active = False

    def move_to(self, new_state: str, duration: int):
        """Transition the asset to a new state and reset the state timer."""
        self.state                 = new_state
        self.days_in_current_state = 0
        self.target_state_duration = duration


# ── Simulation class ──────────────────────────────────────────────────────────

class SupplyChainSimulation:
    """
    Discrete-event simulation of a fleet of returnable assets flowing through
    the supply chain (Warehouse → TransitOut → Customer → TransitIn → Maintenance).

    Args:
        fleet_size           : Initial number of assets in the fleet.
        daily_demand         : Average units shipped per day (can be fractional).
        customer_dwell_mean  : Mean number of days an asset stays at a customer site.
        item_ages            : List of real asset age values (days) to initialise from.
                               If empty, ages are drawn from Uniform(0, 1000).
        eu_exposure_percent  : Fraction of assets subject to EU age regulations.
        eu_max_age_days      : Maximum age (days) before an EU-flagged asset retires.
        auto_replenish       : If True, automatically purchase new assets to replace losses.
    """

    def __init__(
        self,
        fleet_size: int,
        daily_demand: float,
        customer_dwell_mean: int,
        item_ages: list,
        eu_exposure_percent: float,
        eu_max_age_days: int,
        auto_replenish: bool = False
    ):
        self.daily_demand        = daily_demand
        self.customer_dwell_mean = customer_dwell_mean
        self.eu_exposure_percent = eu_exposure_percent
        self.eu_max_age_days     = eu_max_age_days
        self.auto_replenish      = auto_replenish

        # Initialise fleet with realistic age distribution drawn from real data
        def sample_age():
            return random.choice(item_ages) if item_ages else random.randint(0, 1000)

        self.assets = [
            Asset(
                age_days=sample_age(),
                eu_exposure_percent=eu_exposure_percent,
                eu_max_age_days=eu_max_age_days
            )
            for _ in range(fleet_size)
        ]

        self.day                = 0
        self.warehouse_history  = []   # Daily snapshot of assets available in warehouse
        self.total_demand_days  = 0    # Total days on which demand was evaluated
        self.runout_days        = 0    # Days where demand could NOT be fully met

    def _get_demand_today(self) -> int:
        """
        Convert fractional daily demand to a whole number using probabilistic
        rounding. For example, demand=1.3 yields 1 unit 70% of the time and
        2 units 30% of the time — preserving the long-run average exactly.
        """
        base      = int(self.daily_demand)
        remainder = self.daily_demand - base
        extra     = 1 if random.random() < remainder else 0
        return base + extra

    def run_day(self):
        """
        Advance the simulation by one day:
          1. Tick every active asset (age + state timer).
          2. Apply state transitions when an asset's state duration expires.
          3. Count available warehouse stock.
          4. Fulfil today's demand from available stock (or record a stockout).
          5. Optionally replenish lost/retired assets if auto_replenish is enabled.
        """
        self.day       += 1
        warehouse_count = 0

        for asset in self.assets:
            if not asset.active:
                continue

            asset.tick()
            if not asset.active:
                # Asset was retired by EU age limit during tick
                continue

            # ── State machine transitions ────────────────────────────────────
            if asset.state == "TransitOut":
                # Asset arrives at customer site after transit
                if asset.days_in_current_state >= asset.target_state_duration:
                    dwell_days = max(1, int(random.gauss(self.customer_dwell_mean, CUSTOMER_DWELL_STD_DEV)))
                    asset.move_to("Customer", dwell_days)

            elif asset.state == "Customer":
                # Asset is ready to leave customer site
                if asset.days_in_current_state >= asset.target_state_duration:
                    if random.random() < ASSET_LOSS_RATE:
                        # Asset is lost (damaged, stolen, misplaced)
                        asset.active = False
                    else:
                        transit_days = random.randint(TRANSIT_IN_MIN, TRANSIT_IN_MAX)
                        asset.move_to("TransitIn", transit_days)

            elif asset.state == "TransitIn":
                # Asset returns to MLI and enters maintenance
                if asset.days_in_current_state >= asset.target_state_duration:
                    maint_days = random.randint(MAINTENANCE_MIN, MAINTENANCE_MAX)
                    asset.move_to("Maintenance", maint_days)

            elif asset.state == "Maintenance":
                # Maintenance complete — asset returns to warehouse stock
                if asset.days_in_current_state >= asset.target_state_duration:
                    asset.move_to("Warehouse", 0)

            if asset.state == "Warehouse":
                warehouse_count += 1

        # ── Demand fulfilment ────────────────────────────────────────────────
        demand_today  = self._get_demand_today()
        demand_filled = warehouse_count >= demand_today

        if demand_filled:
            # Ship the required number of assets from the warehouse
            assets_to_ship = [a for a in self.assets if a.active and a.state == "Warehouse"][:demand_today]
            for asset in assets_to_ship:
                transit_days = random.randint(TRANSIT_OUT_MIN, TRANSIT_OUT_MAX)
                asset.move_to("TransitOut", transit_days)
        else:
            # Not enough stock — record a stockout day
            self.runout_days += 1

        self.total_demand_days    += 1
        self.warehouse_history.append(warehouse_count)

        # ── Auto-replenishment ───────────────────────────────────────────────
        # If enabled, buy brand-new assets (age=0) to replace any that were lost/retired
        if self.auto_replenish:
            active_count = sum(1 for a in self.assets if a.active)
            shortfall    = len(self.assets) - active_count
            for _ in range(shortfall):
                self.assets.append(Asset(
                    age_days=0,
                    eu_exposure_percent=self.eu_exposure_percent,
                    eu_max_age_days=self.eu_max_age_days
                ))

        # Prune retired assets to keep the list compact
        self.assets = [a for a in self.assets if a.active]


# ── Main entry point ──────────────────────────────────────────────────────────

def run_simulation(
    item_name           = None,
    daily_demand        = None,
    customer_dwell_mean = None,
    target_availability = 0.99,
    eu_max_age_days     = EU_MAX_AGE_DAYS,
    eu_exposure_percent = 0.20,
    auto_replenish      = False,
) -> tuple:
    """
    Find the minimum fleet size that meets the target service level, then
    run a final detailed simulation to produce the inventory chart.

    Args:
        item_name           : Product name (used to load real-world defaults).
        daily_demand        : Override for average daily shipments. Uses item default if None.
        customer_dwell_mean : Override for average dwell time (days). Uses item default if None.
        target_availability : Desired fraction of days with no stockout (e.g. 0.99).
        eu_max_age_days     : Maximum asset age for EU-regulated assets.
        eu_exposure_percent : Fraction of fleet subject to EU age retirement.
        auto_replenish      : Automatically replace lost/retired assets with new ones.

    Returns:
        (optimal_fleet_size, plotly_figure, availability_thresholds)
        where availability_thresholds is a dict mapping availability levels → fleet sizes.
    """
    # ── Step 1: Load item defaults, then apply any user overrides ────────────
    if item_name:
        item_demand, item_dwell, item_fleet_size, item_ages = get_item_defaults(item_name)
    else:
        item_demand, item_dwell, item_fleet_size, item_ages = 100, 10, 200, []

    sim_daily_demand    = daily_demand        if daily_demand        is not None else item_demand
    sim_dwell_mean      = customer_dwell_mean if customer_dwell_mean is not None else item_dwell

    print(f"\n{'='*55}")
    print(f"  Item:           {item_name or 'All Items'}")
    print(f"  Daily Demand:   {sim_daily_demand}")
    print(f"  Dwell Mean:     {sim_dwell_mean} days")
    print(f"  Target Avail.:  {target_availability:.0%}")
    print(f"  EU Exposure:    {eu_exposure_percent:.0%}")
    print(f"  Starting Fleet: {item_fleet_size} assets")
    print(f"{'='*55}\n")

    # ── Step 2: Heuristic bounds for binary search ───────────────────────────
    # Estimate average full loop cycle length (days) to derive a sensible starting range
    avg_cycle_days = (
        (TRANSIT_OUT_MIN + TRANSIT_OUT_MAX) / 2 +
        sim_dwell_mean +
        (TRANSIT_IN_MIN  + TRANSIT_IN_MAX)  / 2 +
        (MAINTENANCE_MIN + MAINTENANCE_MAX) / 2
    )
    baseline_fleet = int(sim_daily_demand * avg_cycle_days)
    search_low     = int(baseline_fleet * 0.9)
    search_high    = int(baseline_fleet * 2.5)

    # ── Step 3: Binary search for the minimum compliant fleet size ───────────
    print("Optimizing Fleet Size via Binary Search...\n")

    best_size  = search_high
    left       = search_low
    right      = search_high

    # Track the smallest fleet size that achieves each availability threshold
    availability_thresholds  = [0.90, 0.95, 0.98, target_availability]
    threshold_best_fleet     = {t: None for t in availability_thresholds}

    while left <= right:
        mid_size = (left + right) // 2

        # Run a warm-up + measurement simulation at this fleet size
        probe_sim = SupplyChainSimulation(
            fleet_size=mid_size,
            daily_demand=sim_daily_demand,
            customer_dwell_mean=sim_dwell_mean,
            item_ages=item_ages,
            eu_exposure_percent=eu_exposure_percent,
            eu_max_age_days=eu_max_age_days,
            auto_replenish=auto_replenish
        )
        # Warm-up phase: let the fleet reach steady state
        for _ in range(WARMUP_DAYS):
            probe_sim.run_day()

        # Reset counters so warm-up days don't skew the availability metric
        probe_sim.runout_days      = 0
        probe_sim.total_demand_days = 0
        probe_sim.warehouse_history = []

        # Measurement phase
        for _ in range(SIMULATION_DAYS):
            probe_sim.run_day()

        availability = (
            1.0 - (probe_sim.runout_days / probe_sim.total_demand_days)
            if probe_sim.total_demand_days > 0
            else 0.0
        )
        print(f"  Fleet Size: {mid_size:,} → Availability: {availability:.2%}")

        # Record the smallest fleet that meets each threshold
        for threshold in availability_thresholds:
            if availability >= threshold:
                current_best = threshold_best_fleet[threshold]
                if current_best is None or mid_size < current_best['size']:
                    threshold_best_fleet[threshold] = {'size': mid_size, 'availability': availability}

        # Binary search: if target met, try smaller; if not, try larger
        if availability >= target_availability:
            best_size = mid_size
            right     = mid_size - 1
        else:
            left = mid_size + 1

    print(f"\n✓ Optimal Fleet Size: {best_size:,}")

    # ── Step 4: Final simulation with the optimal fleet size ─────────────────
    # Run without warm-up so the chart shows full lifecycle from day 1
    final_sim = SupplyChainSimulation(
        fleet_size=best_size,
        daily_demand=sim_daily_demand,
        customer_dwell_mean=sim_dwell_mean,
        item_ages=item_ages,
        eu_exposure_percent=eu_exposure_percent,
        eu_max_age_days=eu_max_age_days,
        auto_replenish=auto_replenish
    )
    for _ in range(SIMULATION_DAYS):
        final_sim.run_day()

    warehouse_history = final_sim.warehouse_history
    days              = list(range(1, len(warehouse_history) + 1))

    # ── Step 5: Build the Plotly chart ───────────────────────────────────────
    fig = go.Figure()

    # Area trace for daily warehouse stock
    fig.add_trace(go.Scatter(
        x=days,
        y=warehouse_history,
        mode='lines',
        name='Warehouse Stock',
        line=dict(color='#4e9af1', width=3),
        fill='tozeroy',
        fillcolor='rgba(78, 154, 241, 0.15)',
        hovertemplate='Day %{x}<br>Stock: %{y}<extra></extra>'
    ))

    # Horizontal stockout reference line at y=0
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#ff4b4b",
        line_width=2,
        annotation_text="Stockout Line",
        annotation_position="bottom right",
        annotation_font_color="#ff4b4b"
    )

    fig.update_layout(
        title=(
            f'<b>Inventory Levels — {item_name or "All Items"}</b>'
            f'  |  {SIMULATION_DAYS} Days<br>'
            f'<span style="font-size:13px;color:gray;">'
            f'Optimal Fleet: {best_size:,}  |  Demand: {sim_daily_demand}'
            f'  |  Dwell: {sim_dwell_mean}d  |  EU: {eu_exposure_percent:.0%}'
            f'</span>'
        ),
        xaxis_title='Simulation Day',
        yaxis_title='Available Assets',
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', zeroline=False)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', zeroline=False)

    # Build a clean dict: {availability_level → fleet_size} (omit unresolved thresholds)
    clean_thresholds = {
        level: result['size']
        for level, result in threshold_best_fleet.items()
        if result is not None
    }

    return best_size, fig, clean_thresholds


# ── Script entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    names = get_item_names()
    if names:
        optimal_size, fig, thresholds = run_simulation(item_name=names[0])
    else:
        optimal_size, fig, thresholds = run_simulation()
    fig.show()
