# app.py (Updated Version)
import streamlit as st
import pandas as pd
import os
import subprocess  # Allows app.py to trigger data_worker.py on the cloud server

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# --- NEW: Cloud Scan Button Control ---
st.sidebar.subheader("🔄 Cloud Data Controls")
if st.sidebar.button("🚀 Trigger Live Market Scan"):
    with st.spinner("Scanning S&P indexes and calculating options chains... This takes 1-2 minutes."):
        # This tells Streamlit's cloud server to run your background worker script
        result = subprocess.run(["python", "data_worker.py"], capture_output=True, text=True)
        st.sidebar.success("✅ Scan Complete!")
        st.rerun()

# Verification Step: Check if data worker spreadsheet exists
if not os.path.exists("options_candidates.csv"):
    # Updated message to match the new capability
    st.warning("⚠️ No scan data found on the server. Please click '🚀 Trigger Live Market Scan' in the sidebar to compile the initial market spreadsheet data.")
else:
    # Read the data file instantly 
    df = pd.read_csv("options_candidates.csv")
    
    # [The rest of your app.py code continues exactly the same as before...]
    tab1, tab2, tab3 = st.tabs(["🔥 Directional Buying (Calls/Puts)", "🛡️ Premium Collection (CSPs)", "📋 All Active Candidates"])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY")]
        if not buying_df.empty:
            st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else:
            st.info("No high-probability directional buying candidates found currently.")
            
    with tab2:
        st.subheader("High-IV Support Retests (Put Writing / CSPs)")
        csp_df = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED")]
        if not csp_df.empty:
            st.dataframe(csp_df, use_container_width=True, hide_index=True)
        else:
            st.info("No premium-selling candidates found.")
            
    with tab3:
        st.subheader("Master Screened Output Board")
        st.dataframe(df, use_container_width=True, hide_index=True)
