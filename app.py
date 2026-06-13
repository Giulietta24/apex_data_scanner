# app.py
import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# Verification Step: Check if data worker spreadsheet exists
if not os.path.exists("options_candidates.csv"):
    st.error("⚠️ No scan data found. Please run 'python data_worker.py' in your local terminal first to compile the initial market spreadsheet data.")
else:
    # Read the data file instantly 
    df = pd.read_csv("options_candidates.csv")
    
    # Render Strategy Categories via Tabs
    tab1, tab2, tab3 = st.tabs(["🔥 Directional Buying (Calls/Puts)", "🛡️ Premium Collection (CSPs)", "📋 All Active Candidates"])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY")]
        if not buying_df.empty:
            st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else:
            st.info("No high-probability directional buying candidates found currently. (IV may be too high market-wide).")
            
    with tab2:
        st.subheader("High-IV Support Retests (Put Writing / CSPs)")
        csp_df = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED")]
        if not csp_df.empty:
            st.dataframe(csp_df, use_container_width=True, hide_index=True)
        else:
            st.info("No premium-selling candidates found. High-IV support zones are not being tested right now.")
            
    with tab3:
        st.subheader("Master Screened Output Board")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    # Single Ticker Interactive Breakdown Panel
    st.markdown("---")
    st.subheader("🔍 Single-Asset Execution Audit")
    selected_ticker = st.selectbox("Select an asset to view specific contract guidelines:", df["Ticker"].unique())
    
    if selected_ticker:
        row = df[df["Ticker"] == selected_ticker].iloc[0]
        action = row["RECOMMENDED ACTION"]
        
        # Color match header blocks based on strategy output
        if "BUY CALLS" in action:
            st.success(f"### {action} CONFIGURATION ACTIVE FOR {selected_ticker}")
        elif "BUY PUTS" in action:
            st.error(f"### {action} CONFIGURATION ACTIVE FOR {selected_ticker}")
        elif "CASH-SECURED" in action:
            st.info(f"### {action} CONFIGURATION ACTIVE FOR {selected_ticker}")
        else:
            st.warning(f"### {action}")
            
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Spot Price", f"${row['Price']}")
        col2.metric("Distance from 20-EMA", row["vs 20-EMA"])
        col3.metric("ATM Contract IV", row["Implied Vol (IV)"])
        col4.metric("Bid-Ask Spread Width", row["ATM Bid-Ask Spread"])
        
        st.markdown(f"**Automated Analysis:** {row['Reasoning Breakdown']}")
        st.info("💡 **Swing Execution Blueprint:** If buying Calls/Puts, target 30-45 Days Out at a 0.50 - 0.60 Delta strike to mitigate decay curves. If selling Cash-Secured Puts, deploy strikes at a 0.30 Delta or lower to maximize your statistical win probability.")