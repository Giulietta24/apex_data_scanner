# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf
import numpy as np

try:
    from data_worker import scan_market
except ImportError:
    st.error("⚠️ Could not find data_worker.py in the same directory.")

st.set_page_config(page_title="Apex Swing Engine", layout="wide")

st.title("🎯 Apex Options Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Holding Window: Days to Weeks")

# --- SIDEBAR CONTROLS ---
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

st.sidebar.markdown("---")

st.sidebar.subheader("🔍 Instant Single-Ticker Audit")
custom_symbol = st.sidebar.text_input("Type any stock symbol (e.g., TSLA, PLTR, IWM):").upper().strip()

# --- MAIN DASHBOARD INTERFACE ---
if custom_symbol:
    st.subheader(f"⚡ Instant On-Demand Audit for: {custom_symbol}")
    with st.spinner(f"Fetching real-time metrics for {custom_symbol}..."):
        try:
            ticker = yf.Ticker(custom_symbol)
            hist = ticker.history(period="3mo")
            
            if hist.empty or len(hist) < 20:
                st.error(f"Could not retrieve sufficient trading data for '{custom_symbol}'.")
            else:
                current_price = hist['Close'].iloc[-1]
                hist['20_EMA'] = hist['Close'].ewm(span=20, adjust=False).mean()
                current_ema = hist['20_EMA'].iloc[-1]
                is_bullish = current_price > current_ema
                trend_pct = ((current_price - current_ema) / current_ema) * 100
                
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
                
                if is_bullish and iv < 35:
                    strategy, status_type = "🟢 BUY CALLS", "success"
                    reason = f"Breakout above 20 EMA. Option IV ({iv:.1f}%) is cheap."
                elif not is_bullish and iv < 50:
                    strategy, status_type = "🔴 BUY PUTS", "error"
                    reason = f"Breakdown below 20 EMA. IV ({iv:.1f}%) has not spiked yet."
                elif is_bullish and iv >= 55:
                    strategy, status_type = "🔵 SELL CASH-SECURED PUTS", "info"
                    reason = f"Bullish trend, but elevated IV ({iv:.1f}%) favors premium sellers."
                else:
                    strategy, status_type = "🟡 STAY IN CASH", "warning"
                    reason = f"Asset sitting inside volatility chop zone ({iv:.1f}% IV)."
                
                if status_type == "success": st.success(f"### Strategy Signal: {strategy}")
                elif status_type == "error": st.error(f"### Strategy Signal: {strategy}")
                elif status_type == "info": st.info(f"### Strategy Signal: {strategy}")
                else: st.warning(f"### Strategy Signal: {strategy}")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Spot Price", f"${current_price:.2f}")
                col2.metric("Distance from 20-EMA", f"{trend_pct:+.1f}%")
                col3.metric("ATM Contract IV", f"{iv:.1f}%")
                col4.metric("Open Interest Depth", f"{open_interest}")
                st.markdown(f"**Analysis:** {reason}")
                st.markdown("---")
        except Exception as err:
            st.error(f"Failed to scan {custom_symbol}: {err}")

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
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔥 Directional Buying (Calls/Puts)", 
        "🛡️ Premium Collection (CSPs)", 
        "📋 All Active Candidates",
        "🔍 Hidden Audit Trail (Rejected Names)",
        "📊 Interactive Backtest Engine"
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

    with tab5:
        st.subheader("⚙️ Run a Historical Backtest Simulation")
        st.caption("Simulate performance across the specific strategy configurations.")
        
        # Extended User Inputs
        bt_col1, bt_col2, bt_col3, bt_col4, bt_col5 = st.columns(5)
        bt_symbol = bt_col1.text_input("Ticker to Backtest:", value="SPY").upper().strip()
        
        # NEW: DROPDOWN FOR SELECTING STRATEGY REGIME
        bt_strategy = bt_col2.selectbox("Strategy to Test:", ["🟢 BUY CALLS (Bullish)", "🔴 BUY PUTS (Bearish)", "🔵 SELL CSPs (Premium Collection)"])
        
        bt_years = bt_col3.slider("Horizon (Years)", min_value=1, max_value=5, value=3)
        bt_target = bt_col4.slider("Profit Target (%)", min_value=1, max_value=15, value=5) / 100
        bt_stop = bt_col5.slider("Stop Loss (%)", min_value=1, max_value=10, value=3) / 100
        
        if st.button("📈 Execute Historical Backtest"):
            with st.spinner(f"Running historical simulation..."):
                try:
                    bt_ticker = yf.Ticker(bt_symbol)
                    bt_df = bt_ticker.history(period=f"{bt_years}y")
                    
                    if bt_df.empty or len(bt_df) < 50:
                        st.error("Insufficient historical records found.")
                    else:
                        bt_df['20_EMA'] = bt_df['Close'].ewm(span=20, adjust=False).mean()
                        in_pos = False
                        ent_price = 0
                        ent_date = None
                        sim_trades = []
                        
                        for idx in range(20, len(bt_df)):
                            c_date = bt_df.index[idx]
                            c_close = bt_df['Close'].iloc[idx]
                            p_close = bt_df['Close'].iloc[idx-1]
                            c_ema = bt_df['20_EMA'].iloc[idx]
                            p_ema = bt_df['20_EMA'].iloc[idx-1]
                            
                            if not in_pos:
                                # CALLS: Enter when price breaks ABOVE 20-EMA
                                if "BUY CALLS" in bt_strategy and p_close <= p_ema and c_close > c_ema:
                                    in_pos, ent_price, ent_date = True, c_close, c_date
                                # PUTS: Enter when price breaks BELOW 20-EMA
                                elif "BUY PUTS" in bt_strategy and p_close >= p_ema and c_close < c_ema:
                                    in_pos, ent_price, ent_date = True, c_close, c_date
                                # CSPs: Enter on pullbacks holding ABOVE 20-EMA
                                elif "SELL CSPs" in bt_strategy and p_close > p_ema and c_close > c_ema and (c_close - c_ema)/c_ema < 0.01:
                                    in_pos, ent_price, ent_date = True, c_close, c_date
                            else:
                                # Calculate Directional Gains
                                if "BUY PUTS" in bt_strategy:
                                    return_pct = (ent_price - c_close) / ent_price  # Profits when price falls
                                else:
                                    return_pct = (c_close - ent_price) / ent_price  # Profits when price rises
                                    
                                trade_days = (c_date - ent_date).days
                                
                                if return_pct >= bt_target:
                                    sim_trades.append({"Entry Date": ent_date.strftime('%Y-%m-%d'), "Exit Date": c_date.strftime('%Y-%m-%d'), "Performance": f"+{bt_target*100:.1f}%", "Result": "WIN"})
                                    in_pos = False
                                elif return_pct <= -bt_stop:
                                    sim_trades.append({"Entry Date": ent_date.strftime('%Y-%m-%d'), "Exit Date": c_date.strftime('%Y-%m-%d'), "Performance": f"-{bt_stop*100:.1f}%", "Result": "LOSS"})
                                    in_pos = False
                                elif trade_days >= 30:
                                    sim_trades.append({"Entry Date": ent_date.strftime('%Y-%m-%d'), "Exit Date": c_date.strftime('%Y-%m-%d'), "Performance": f"{return_pct*100:+.1f}%", "Result": "TIMEOUT"})
                                    in_pos = False
                                    
                        if not sim_trades:
                            st.info("No trading signals matched these rules in the specified timeframe.")
                        else:
                            t_df = pd.DataFrame(sim_trades)
                            total_t = len(t_df)
                            wins_t = len(t_df[t_df['Result'] == 'WIN'])
                            win_rate_t = (wins_t / total_t) * 100
                            
                            m_col1, m_col2, m_col3 = st.columns(3)
                            m_col1.metric("Total Trades Simulated", f"{total_t} Setups")
                            m_col2.metric("Strategy Win Rate", f"{win_rate_t:.1f}%")
                            
                            b_and_h = ((bt_df['Close'].iloc[-1] - bt_df['Close'].iloc[0]) / bt_df['Close'].iloc[0]) * 100
                            m_col3.metric("Benchmark Buy & Hold", f"{b_and_h:+.1f}%")
                            
                            st.subheader("Detailed Trade Ledger")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Backtester error: {e}")
