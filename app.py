# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf

try:
    from data_worker import scan_market
except ImportError:
    st.error("⚠️ Could not find data_worker.py in the same directory.")

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# --- SIDEBAR CONTROLS ---
st.sidebar.subheader("🔄 Cloud Data Controls")

# 1. Existing Broad Scan Button
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

st.sidebar.markdown("---")

# 2. NEW: Custom Ticker Manual Audit Box
st.sidebar.subheader("🔍 Instant Single-Ticker Audit")
custom_symbol = st.sidebar.text_input("Type any stock symbol (e.g., TSLA, PLTR, IWM):").upper().strip()

# --- MAIN DASHBOARD INTERFACE ---

# If the user typed a custom ticker, we process it instantly right here!
if custom_symbol:
    st.subheader(f"⚡ Instant On-Demand Audit for: {custom_symbol}")
    with st.spinner(f"Fetching real-time options metrics for {custom_symbol}..."):
        try:
            ticker = yf.Ticker(custom_symbol)
            hist = ticker.history(period="3mo")
            
            if hist.empty or len(hist) < 20:
                st.error(f"Could not retrieve sufficient trading data for '{custom_symbol}'. Check the symbol spelling.")
            else:
                current_price = hist['Close'].iloc[-1]
                hist['20_EMA'] = hist['Close'].ewm(span=20, adjust=False).mean()
                current_ema = hist['20_EMA'].iloc[-1]
                is_bullish = current_price > current_ema
                trend_pct = ((current_price - current_ema) / current_ema) * 100
                
                # Default Option Values if data is restricted
                iv, open_interest, spread_pct = 32.0, 1000, 0.5
                try:
                    expirations = ticker.options
                    if expirations:
                        target_expiry = expirations[min(2, len(expirations)-1)]
                        opt_chain = ticker.option_chain(target_expiry)
                        calls = opt_chain.calls
                        if not calls.empty:
                            calls['strike_diff'] = (calls['strike'] - current_price).abs()
                            atm_call = calls.sort_values(by='strike_diff').iloc[0]
                            iv = (atm_call['impliedVolatility'] * 100) if pd.notnull(atm_call.get('impliedVolatility')) else 32.0
                            open_interest = int(atm_call['openInterest']) if pd.notnull(atm_call.get('openInterest')) else 1000
                except:
                    pass
                
                # Evaluate Strategy Matrix
                if is_bullish and iv < 35:
                    strategy, color, status_type = "🟢 BUY CALLS", "green", "success"
                    reason = f"Breakout above 20 EMA. Option IV ({iv:.1f}%) is cheap for premium buying."
                elif not is_bullish and iv < 50:
                    strategy, color, status_type = "🔴 BUY PUTS", "red", "error"
                    reason = f"Breakdown below 20 EMA. IV ({iv:.1f}%) has not experienced a panic spike yet."
                elif is_bullish and iv >= 55:
                    strategy, color, status_type = "🔵 SELL CASH-SECURED PUTS", "blue", "info"
                    reason = f"Bullish trend framework holding, but elevated IV ({iv:.1f}%) provides rich CSP premium collection support."
                else:
                    strategy, color, status_type = "🟡 STAY IN CASH", "orange", "warning"
                    reason = f"Asset sitting inside volatility chop zone ({iv:.1f}% IV). Insufficient directional edge."
                
                # Display Results in a Clean Box
                if status_type == "success": st.success(f"### Strategy Signal: {strategy}")
                elif status_type == "error": st.error(f"### Strategy Signal: {strategy}")
                elif status_type == "info": st.info(f"### Strategy Signal: {strategy}")
                else: st.warning(f"### Strategy Signal: {strategy}")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Spot Price", f"${current_price:.2f}")
                col2.metric("Distance from 20-EMA", f"{trend_pct:+.1f}%")
                col3.metric("ATM Contract IV", f"{iv:.1f}%")
                col4.metric("Open Interest Depth", f"{open_interest}")
                
                st.markdown(f"**Automated Analysis Breakdown:** {reason}")
                st.markdown("---")
        except Exception as err:
            st.error(f"Failed to scan {custom_symbol}: {err}")

# --- REST OF THE CODE (Displays the background index data tables as usual) ---
if not os.path.exists("options_candidates.csv"):
    st.warning("⚠️ No broad scan data found on the server. Please click '🚀 Trigger Live Market Scan' in the sidebar.")
else:
    df = pd.read_csv("options_candidates.csv")
    
    total_scanned = len(df)
    passed_action = len(df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED")])
    stay_cash = len(df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH")])
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("📋 Total Universe Audited", f"{total_scanned} Tickers")
    col_b.metric("🔥 Actionable Setups Found", f"{passed_action} Stocks")
    col_c.metric("🛡️ Filtered (Stayed in Cash)", f"{stay_cash} Stocks")
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔥 Directional Buying (Calls/Puts)", 
        "🛡️ Premium Collection (CSPs)", 
        "📋 All Active Candidates",
        "🔍 Hidden Audit Trail (Rejected Names)"
    ])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY", na=False)]
        if not buying_df.empty: st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else: st.info("No high-probability directional buying candidates found currently.")
            
    with tab2:
        st.subheader("High-IV Support Retests (Put Writing / CSPs)")
        csp_df = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED", na=False)]
        if not csp_df.empty: st.dataframe(csp_df, use_container_width=True, hide_index=True)
        else: st.info("No premium-selling candidates found.")
            
    with tab3:
        st.subheader("Master Screened Output Board")
        active_df = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]
        st.dataframe(active_df, use_container_width=True, hide_index=True)
        
    with tab4:
        st.subheader("Stocks Evaluated and Intentionally Blocked by Filters")
        rejected_df = df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)]
        st.dataframe(rejected_df[["Ticker", "Price", "vs 20-EMA", "Implied Vol (IV)", "RECOMMENDED ACTION", "Reasoning Breakdown"]], use_container_width=True, hide_index=True)
