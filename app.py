# app.py
import streamlit as st
import pandas as pd
import os

try:
    from data_worker import scan_market
except ImportError:
    st.error("⚠️ Could not find data_worker.py in the same directory.")

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# --- Cloud Scan Control Panel ---
st.sidebar.subheader("🔄 Cloud Data Controls")

if st.sidebar.button("🚀 Trigger Live Market Scan"):
    with st.status("🕵️‍♂️ Crawling Indexes & Analyzing Options Chains...", expanded=True) as status:
        try:
            scan_market() 
            status.update(label="✅ Live Market Scan Complete!", state="complete", expanded=False)
            st.sidebar.success("Data Refreshed!")
            st.rerun()
        except Exception as e:
            status.update(label="❌ Scan Failed", state="error")
            st.error(f"Server Processing Error: {e}")

# Verification Step: Check if data worker spreadsheet exists
if not os.path.exists("options_candidates.csv"):
    st.warning("⚠️ No scan data found on the server. Please click '🚀 Trigger Live Market Scan' in the sidebar.")
else:
    df = pd.read_csv("options_candidates.csv")
    
    # --- NEW: MASTER AUDIT COUNTERS ---
    # This proves to you mathematically that every single asset was evaluated
    total_scanned = len(df)
    passed_action = len(df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED")])
    stay_cash = len(df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH")])
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("📋 Total Universe Audited", f"{total_scanned} Tickers")
    col_b.metric("🔥 Actionable Setups Found", f"{passed_action} Stocks")
    col_c.metric("🛡️ Filtered (Stayed in Cash)", f"{stay_cash} Stocks")
    st.markdown("---")
    
    # Render Strategy Categories via Tabs (Adding a 4th tab for transparency)
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔥 Directional Buying (Calls/Puts)", 
        "🛡️ Premium Collection (CSPs)", 
        "📋 All Active Candidates",
        "🔍 Hidden Audit Trail (Rejected Names)"
    ])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY", na=False)]
        if not buying_df.empty:
            st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else:
            st.info("No high-probability directional buying candidates found currently.")
            
    with tab2:
        st.subheader("High-IV Support Retests (Put Writing / CSPs)")
        csp_df = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED", na=False)]
        if not csp_df.empty:
            st.dataframe(csp_df, use_container_width=True, hide_index=True)
        else:
            st.info("No premium-selling candidates found.")
            
    with tab3:
        st.subheader("Master Screened Output Board")
        active_df = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]
        st.dataframe(active_df, use_container_width=True, hide_index=True)
        
    with tab4:
        st.subheader("Stocks Evaluated and Intentionally Blocked by Filters")
        st.caption("These stocks were checked by the engine but failed your strategy matrix rules (e.g., IV too high, or stuck in chop zones).")
        rejected_df = df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)]
        st.dataframe(rejected_df[["Ticker", "Price", "vs 20-EMA", "Implied Vol (IV)", "RECOMMENDED ACTION", "Reasoning Breakdown"]], use_container_width=True, hide_index=True)
