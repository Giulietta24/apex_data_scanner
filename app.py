# app.py
import streamlit as st
import pandas as pd
import os

# Import the scanning engine directly from your other file
try:
    from data_worker import scan_market
except ImportError:
    st.error("⚠️ Could not find data_worker.py in the same directory. Please ensure both files are pushed to GitHub.")

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# --- Cloud Scan Control Panel ---
st.sidebar.subheader("🔄 Cloud Data Controls")

if st.sidebar.button("🚀 Trigger Live Market Scan"):
    # This creates a loading box on your screen so you know the server is active
    with st.status("🕵️‍♂️ Crawling Indexes & Analyzing Options Chains...", expanded=True) as status:
        try:
            st.write("Fetching real-time market data from indices...")
            # Run the function directly within the Streamlit process
            scan_market() 
            
            status.update(label="✅ Live Market Scan Complete!", state="complete", expanded=False)
            st.sidebar.success("Data Refreshed!")
            st.rerun()
        except Exception as e:
            status.update(label="❌ Scan Failed", state="error")
            st.error(f"Server Processing Error: {e}")

# Verification Step: Check if data worker spreadsheet exists
if not os.path.exists("options_candidates.csv"):
    st.warning("⚠️ No scan data found on the server. Please click '🚀 Trigger Live Market Scan' in the sidebar to compile the initial market spreadsheet data.")
else:
    # Read the data file instantly 
    df = pd.read_csv("options_candidates.csv")
    
    # Render Strategy Categories via Tabs
    tab1, tab2, tab3 = st.tabs(["🔥 Directional Buying (Calls/Puts)", "🛡️ Premium Collection (CSPs)", "📋 All Active Candidates"])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        if "RECOMMENDED ACTION" in df.columns:
            buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY", na=False)]
            if not buying_df.empty:
                st.dataframe(buying_df, use_container_width=True, hide_index=True)
            else:
                st.info("No high-probability directional buying candidates found currently.")
            
    with tab2:
        st.subheader("High-IV Support Retests (Put Writing / CSPs)")
        if "RECOMMENDED ACTION" in df.columns:
            csp_df = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED", na=False)]
            if not csp_df.empty:
                st.dataframe(csp_df, use_container_width=True, hide_index=True)
            else:
                st.info("No premium-selling candidates found.")
            
    with tab3:
        st.subheader("Master Screened Output Board")
        st.dataframe(df, use_container_width=True, hide_index=True)
