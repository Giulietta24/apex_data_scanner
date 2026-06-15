# app.py
import streamlit as st
import pandas as pd
import os
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

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
custom_symbol = st.sidebar.text_input("Type any stock symbol (e.g., TSLA, PLTR, RKLB):").upper().strip()

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
                
                iv, open_interest = 32.0, 1000
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
                
                if iv > 100:
                    strategy, status_type = "⚠️ STAY IN CASH", "warning"
                    reason = f"Asset sitting inside volatility chop zone ({iv:.1f}% IV). Insufficient directional edge."
                elif is_bullish and iv < 35:
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
                st.markdown(f"**Automated Analysis Breakdown:** {reason}")
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
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔥 Directional Buying (Calls/Puts)", 
        "🛡️ Premium Collection (CSPs)", 
        "🛰️ Idiosyncratic Alpha Screen",
        "📋 All Active Candidates",
        "🔍 Hidden Audit Trail (Rejected Names)",
        "🔮 Advanced Future-Probability Backtester"
    ])
    
    with tab1:
        st.subheader("Low-IV Trend Breaks (Option Buying)")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY", na=False)]
        if not buying_df.empty: st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else: st.info("No high-probability directional buying candidates found currently.")
            
    with tab2:
        st.subheader("🛡️ Strategic CSP Premium Deployment Console")
        st.caption("Farms elevated Implied Volatility to collect income or acquire equity at a structural discount.")
        
        csp_base = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED", na=False)].copy()
        
        if csp_base.empty:
            st.info("No high-IV premium-selling candidates found right now.")
        else:
            # 📅 Compute Precise Calendar Windows (30 to 45 Days to Expiration)
            today = datetime.now()
            opt_min_date = (today + timedelta(days=30)).strftime("%Y-%m-%b")
            opt_max_date = (today + timedelta(days=45)).strftime("%Y-%m-%b")
            
            # 🧮 Compute Intent-Based Math Vectors
            csp_base["Spot"] = csp_base["Price"].apply(lambda x: float(str(x).replace('$','').strip()))
            
            # Income: Targets ~0.30 Delta (~7-8% lower than spot on high-IV assets)
            csp_base["🎯 INCOME Play Strike"] = (csp_base["Spot"] * 0.93).apply(lambda x: f"${round(x * 2) / 2:.2f}")
            # Discount Acquisition: Targets deep support cushion (12% lower than spot)
            csp_base["🛍️ DISCOUNT Play Strike"] = (csp_base["Spot"] * 0.88).apply(lambda x: f"${round(x * 2) / 2:.2f}")
            
            # Format Output View
            csp_base["Look For Expirations Between"] = f"{opt_min_date} and {opt_max_date}"
            
            final_view = csp_base[["Ticker", "Price", "Implied Vol (IV)", "Look For Expirations Between", "🎯 INCOME Play Strike", "🛍️ DISCOUNT Play Strike"]]
            st.dataframe(final_view, use_container_width=True, hide_index=True)
            
            st.markdown(f"""
            ---
            ### 📌 Operational Playbook for This Batch
            
            * **Calendar Focus Window:** Open your broker panel and look strictly at expiration dates between **{opt_min_date}** and **{opt_max_date}**. 
            
            * **Option A: The Pure Income Play (Keep the Cash)**
              * **Intent:** You do not want to own the stock; you just want to stack cash.
              * **Execution:** Sell the **🎯 INCOME Play Strike** option. It aligns roughly with a **0.30 Delta**, giving you an immediate cushion while capturing maximum Theta decay velocity.
              * **Exit Management:** Set an automatic GTC limit order to buy back the contract the second it drops to **50% of the initial premium collected**.
              
            * **Option B: The Value Investor Play (Buy the Discount)**
              * **Intent:** You love the company's alpha profile and want to buy shares, but refuse to pay full retail price.
              * **Execution:** Sell the **🛍️ DISCOUNT Play Strike** option. If the stock flushes, you get assigned shares at a deep structural markdown. If it bounces, you get paid to wait.
              * **Exit Management:** Hold to expiration day to secure maximum markdown or assignment.
            """)

    with tab3:
        st.subheader("🛰️ Market-Decoupled Alpha Matrix")
        st.caption("Scans active candidates using real-time sync to pinpoint tickers whose setups survive independent of S&P 500 market risk.")
        
        active_candidates = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]["Ticker"].unique().tolist()
        
        if not active_candidates:
            st.info("No active candidates currently available to screen for Alpha.")
        else:
            if st.button("🛰️ Extract Market-Decoupled Alpha"):
                alpha_leads = []
                with st.spinner(f"Extracting historical beta values across {len(active_candidates)} assets..."):
                    try:
                        spy_h = yf.Ticker("SPY").history(period="3y")
                        for sym in active_candidates:
                            a_h = yf.Ticker(sym).history(period="3y")
                            if a_h.empty or len(a_h) < 200: continue
                            
                            c_df = a_h.join(spy_h['Close'].rename('SPY_Close'), how='inner')
                            c_df['20_EMA'] = c_df['Close'].ewm(span=20, adjust=False).mean()
                            c_df['SPY_200_EMA'] = c_df['SPY_Close'].ewm(span=200, adjust=False).mean()
                            
                            in_pos, ent_p, win_macro, tot_macro, win_div, tot_div = False, 0.0, 0, 0, 0, 0
                            
                            for idx in range(200, len(c_df)):
                                if not in_pos:
                                    if c_df['Close'].iloc[idx-1] <= c_df['20_EMA'].iloc[idx-1] and c_df['Close'].iloc[idx] > c_df['20_EMA'].iloc[idx]:
                                        in_pos = True
                                        ent_p = float(c_df['Close'].iloc[idx])
                                        is_macro_b = c_df['SPY_Close'].iloc[idx] > c_df['SPY_200_EMA'].iloc[idx]
                                        t_type = "MACRO" if is_macro_b else "DIV"
                                        days_in = 0
                                else:
                                    days_in += 1
                                    ret = (c_df['Close'].iloc[idx] - ent_p) / ent_p
                                    if ret >= 0.10:
                                        if t_type == "MACRO": win_macro += 1; tot_macro += 1
                                        else: win_div += 1; tot_div += 1
                                        in_pos = False
                                    elif ret <= -0.05:
                                        if t_type == "MACRO": tot_macro += 1
                                        else: tot_div += 1
                                        in_pos = False
                                    elif days_in >= 21:
                                        in_pos = False
                            
                            m_wr = (win_macro / tot_macro * 100) if tot_macro > 0 else 0.0
                            d_wr = (win_div / tot_div * 100) if tot_div > 0 else 0.0
                            
                            if d_wr >= 45.0:
                                row_info = df[df["Ticker"] == sym].iloc[0]
                                current_iv = row_info["Implied Vol (IV)"]
                                clean_iv = float(str(current_iv).replace('%','').strip()) if pd.notnull(current_iv) else 30.0
                                
                                play = "🟢 BUY CALLS" if clean_iv < 50 else "🔵 SELL CSPs (High IV Yield)"
                                alpha_leads.append({
                                    "Ticker": sym,
                                    "Macro Bull Win Rate": f"{m_wr:.1f}%",
                                    "Divergent Bear Win Rate": f"{d_wr:.1f}%",
                                    "Alpha Score": f"+{(d_wr - 40.0):.1f}",
                                    "Optimal Exploitation Play": play
                                })
                                
                        if alpha_leads:
                            st.success(f"🎯 Successfully isolated {len(alpha_leads)} Idiosyncratic Alpha Engines!")
                            st.dataframe(pd.DataFrame(alpha_leads).sort_values(by="Alpha Score", ascending=False), use_container_width=True, hide_index=True)
                        else:
                            st.warning("All current assets show high correlation to market trends. No uncoupled Alpha detected in this batch.")
                    except Exception as ex:
                        st.error(f"Alpha Sorting Engine Interrupted: {ex}")
            
    with tab4:
        st.subheader("Master Screened Output Board")
        active_df = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]
        st.dataframe(active_df, use_container_width=True, hide_index=True)
        
    with tab5:
        st.subheader("Stocks Evaluated and Intentionally Blocked by Filters")
        rejected_df = df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)]
        st.dataframe(rejected_df[["Ticker", "Price", "vs 20-EMA", "Implied Vol (IV)", "RECOMMENDED ACTION", "Reasoning Breakdown"]], use_container_width=True, hide_index=True)

    with tab6:
        st.subheader("🔮 Advanced Future-Probability Backtest Engine")
        st.caption("Filters historical setups through Macro Regimes to model real option outcomes.")
        
        # User Controls
        bt_col1, bt_col2, bt_col3, bt_col4, bt_col5 = st.columns(5)
        bt_symbol = bt_col1.text_input("Ticker to Predict:", value="TSLA").upper().strip()
        bt_strategy = bt_col2.selectbox("Option Flow Type:", ["🟢 BUY CALLS (Bullish)", "🔴 BUY PUTS (Bearish)"])
        bt_years = bt_col3.slider("Backtest Lookback Horizon (Years)", min_value=1, max_value=5, value=3)
        bt_target = bt_col4.slider("Take Profit (%)", min_value=1, max_value=20, value=10) / 100
        bt_stop = bt_col5.slider("Stop Loss (%)", min_value=1, max_value=15, value=5) / 100
        
        if st.button("🔮 Calculate Predictive Probability Matrix"):
            with st.spinner("Analyzing Macro Conditions & Volatility Regimes..."):
                try:
                    asset_df = yf.Ticker(bt_symbol).history(period=f"{bt_years}y")
                    spy_df = yf.Ticker("SPY").history(period=f"{bt_years}y")
                    
                    if asset_df.empty or spy_df.empty:
                        st.error("Missing synchronization records.")
                    else:
                        combined_df = asset_df.join(spy_df['Close'].rename('SPY_Close'), how='inner')
                        combined_df['20_EMA'] = combined_df['Close'].ewm(span=20, adjust=False).mean()
                        combined_df['SPY_200_EMA'] = combined_df['SPY_Close'].ewm(span=200, adjust=False).mean()
                        
                        in_pos = False
                        ent_price = 0.0
                        ent_date = None
                        trade_regime = ""
                        sim_trades = []
                        
                        for idx in range(200, len(combined_df)):
                            c_date = combined_df.index[idx]
                            c_close = combined_df['Close'].iloc[idx]
                            p_close = combined_df['Close'].iloc[idx-1]
                            c_ema = combined_df['20_EMA'].iloc[idx]
                            p_ema = combined_df['20_EMA'].iloc[idx-1]
                            
                            spy_price = combined_df['SPY_Close'].iloc[idx]
                            spy_ema200 = combined_df['SPY_200_EMA'].iloc[idx]
                            macro_bullish = spy_price > spy_ema200
                            
                            if not in_pos:
                                if "BUY CALLS" in bt_strategy and p_close <= p_ema and c_close > c_ema:
                                    in_pos = True
                                    ent_price = float(c_close)
                                    ent_date = c_date
                                    trade_regime = "🟢 BULLISH MACRO" if macro_bullish else "⚠️ BEAR TRAP RISK"
                                elif "BUY PUTS" in bt_strategy and p_close >= p_ema and c_close < c_ema:
                                    in_pos = True
                                    ent_price = float(c_close)
                                    ent_date = c_date
                                    trade_regime = "🔴 BEARISH MACRO" if not macro_bullish else "⚠️ BULL TRAP RISK"
                            else:
                                if "BUY PUTS" in bt_strategy:
                                    return_pct = (ent_price - c_close) / ent_price
                                else:
                                    return_pct = (c_close - ent_price) / ent_price
                                    
                                trade_days = (c_date - ent_date).days
                                
                                if return_pct >= bt_target:
                                    sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "WIN", "Real Option Est": f"+{bt_target*250:.0f}% 🔥"})
                                    in_pos = False
                                elif return_pct <= -bt_stop:
                                    sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "LOSS", "Real Option Est": f"-{bt_stop*150:.0f}% 💀"})
                                    in_pos = False
                                elif trade_days >= 21:
                                    sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "TIMEOUT", "Real Option Est": f"{return_pct*100:+.1f}% ⏳"})
                                    in_pos = False
                                    
                        if not sim_trades:
                            st.info("No system signals triggered under these combined rules.")
                        else:
                            t_df = pd.DataFrame(sim_trades)
                            bull_setups = t_df[t_df['Regime State'].str.contains("BULLISH MACRO|BEARISH MACRO", na=False)]
                            trap_setups = t_df[t_df['Regime State'].str.contains("RISK", na=False)]
                            
                            win_rate_macro = (len(bull_setups[bull_setups['Result'] == 'WIN']) / len(bull_setups) * 100) if len(bull_setups) > 0 else 0.0
                            win_rate_trap = (len(trap_setups[trap_setups['Result'] == 'WIN']) / len(trap_setups) * 100) if len(trap_setups) > 0 else 0.0
                            
                            st.subheader("🔮 Predictive Probability Ledger")
                            pa, pb = st.columns(2)
                            pa.metric("Probability when Macro Confirmed", f"{win_rate_macro:.1f}% Win Rate")
                            pb.metric("Probability during Market Divergence", f"{win_rate_trap:.1f}% Win Rate")
                            
                            st.markdown("### Estimated Real-World Options Outcomes")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                            
                except Exception as e:
                    st.error(f"Probability Engine Error: {e}")
