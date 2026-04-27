"""
pages/forecasting.py
--------------------
Forecasting & Supply Chain Analysis — placeholder page.

This module will eventually include:
  - Demand forecasting (Prophet / ARIMA)
  - Sankey flow diagrams
  - Customer-level deep dives
"""

import streamlit as st


def render():
    """Render the Forecasting & Supply Chain Analysis page."""

    st.markdown('''
    <div style="margin-bottom:28px;">
        <h1 style="font-size:2.4rem;font-weight:800;margin:0 0 4px;
                   background:linear-gradient(135deg,#ffffff 0%,#a0aec0 100%);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            📈 Forecasting &amp; Supply Chain Analysis
        </h1>
        <p style="color:#8892b0;font-size:1rem;margin:0;">
            Demand forecasting, Sankey flow analysis, and supply chain intelligence
        </p>
    </div>
    ''', unsafe_allow_html=True)

    st.info(
        "🚧 **Forecasting module under development.** "
        "This page will include demand forecasting (Prophet/ARIMA), "
        "Sankey flow diagrams, and customer-level deep dives.",
        icon="📈",
    )
