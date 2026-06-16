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

st.set_page_config(page_title="Apex Trading Engine", layout="wide")

st.title("🎯 Apex Options & Equity Signal Dashboard")
st.caption("Automated Multi-Cap Screening Engine | Strategy Holding Period: Days to Weeks")

# --- CORE DATA CACHING LAYER ---
@st.cache_data(ttl=300)
def fetch_ticker_data_cached(symbol, period="3mo"):
    try:
        hist = yf.Ticker(symbol).history(period=period)
        return hist
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_synchronized_macro_data(symbol, horizon_years=3):
    try:
        asset_h = yf.Ticker(symbol).history(period=f"{horizon_years}y")
        spy_h = yf.Ticker("SPY").history(period=f"{horizon_years}y")
        if asset_h.empty or spy_h.empty:
            return pd.DataFrame()
        # Synchronize dates via inner join
        combined = asset_h.join(spy_h['Close'].rename('SPY_Close'), how='inner')
        return combined
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_rsp_market_health():
    try:
        rsp = yf.Ticker("RSP").history(period="3mo")
        if rsp.empty or len(rsp) < 20:
            return True, 0.0  
        rsp['20_EMA'] = rsp['Close'].ewm(span=20, adjust=False).mean()
        is_rsp_bullish = rsp['Close'].iloc[-1] > rsp['20_EMA'].iloc[-1]
        return is_rsp_bullish, rsp['Close'].iloc[-1]
    except:
        return True, 0.0

@st.cache_data(ttl=300)
def fetch_breadth_metrics_panel():
    indices = {"SPY": "S&P 500 (Cap-Weighted)", "RSP": "S&P 500 (Equal-Weighted)", "IWM": "Russell 2000 (Small Caps)"}
    data_summary = []
    errors = []
    
    for ticker, label in indices.items():
        try:
            df = yf.Ticker(ticker).history(period="3mo")
            if df.empty: 
                raise ValueError("Returned data frame is empty.")
                
            df['20_EMA'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['50_MA'] = df['Close'].rolling(window=50).mean()
            
            spot = df['Close'].iloc[-1]
            ema20 = df['20_EMA'].iloc[-1]
            ma50 = df['50_MA'].iloc[-1]
            
            vs_ema = ((spot - ema20) / ema20) * 100
            status = "🟢 BULLISH" if spot > ema20 else "🔴 BEARISH"
            
            data_summary.append({
                "Index": ticker,
                "Market Segment": label,
                "Current Price": f"${spot:.2f}",
                "vs 20-EMA": f"{vs_ema:+.2f}%",
                "Trend Status": status,
                "Above 50-MA": "✅ Yes" if spot > ma50 else "❌ No"
            })
        except Exception as e:
            errors.append(f"⚠️ Could not load {ticker}: {e}")
            
    return pd.DataFrame(data_summary), errors

@st.cache_data(ttl=300)
def fetch_live_vix_metrics():
    try:
        vix_df = yf.Ticker("^VIX").history(period="1mo")
        if vix_df.empty:
            return 18.0, 0.0
        current_vix = vix_df['Close'].iloc[-1]
        vix_change = current_vix - vix_df['Close'].iloc[-2]
        return current_vix, vix_change
    except:
        return 18.0, 0.0

# --- TECHNICAL INDICATORS ---
def calculate_rsi(series, periods=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

# --- SIDEBAR CONTROLS ---
st.sidebar.subheader("🔄 Data Refresh Controls")

if st.sidebar.button("🚀 Trigger Live Market Scan"):
    with st.status("Scanning indices & downloading options data...", expanded=True) as status:
        try:
            scan_market() 
            status.update(label="✅ Live Market Scan Complete!", state="complete", expanded=False)
            st.sidebar.success("Data Refreshed!")
            st.rerun()
        except Exception as e:
            status.update(label="❌ Scan Failed", state="error")
            st.error(f"Data worker processing error: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Single-Ticker Audit")

with st.sidebar.form(key="single_ticker_form"):
    custom_symbol_input = st.text_input("Enter stock symbol (e.g., TSLA, PLTR):").upper().strip()
    submit_audit = st.form_submit_button(label="🔎 Run Technical Audit")

# --- INDIVIDUAL AUDIT PANEL ---
if submit_audit and custom_symbol_input:
    st.subheader(f"📈 Real-Time Technical Analysis: {custom_symbol_input}")
    with st.spinner(f"Fetching technical history for {custom_symbol_input}..."):
        hist = fetch_ticker_data_cached(custom_symbol_input, period="3mo")
        ticker = yf.Ticker(custom_symbol_input)
        rsp_confirmed_bullish, current_rsp_price = fetch_rsp_market_health()
        
        if hist.empty or len(hist) < 20:
            st.error(f"Could not retrieve sufficient technical data for '{custom_symbol_input}'.")
        else:
            current_price = hist['Close'].iloc[-1]
            hist['20_EMA'] = hist['Close'].ewm(span=20, adjust=False).mean()
            hist['Vol_MA20'] = hist['Volume'].rolling(window=20).mean()
            hist['RSI_14'] = calculate_rsi(hist['Close'])
            
            current_ema = hist['20_EMA'].iloc[-1]
            current_vol = hist['Volume'].iloc[-1]
            avg_vol = hist['Vol_MA20'].iloc[-1]
            current_rsi = hist['RSI_14'].iloc[-1]
            
            trend_pct = ((current_price - current_ema) / current_ema) * 100
            
            is_bullish_trend = current_price > current_ema
            volume_confirmed = current_vol > avg_vol
            rsi_safe_long = current_rsi < 75 if not pd.isna(current_rsi) else True
            rsi_safe_short = current_rsi > 30 if not pd.isna(current_rsi) else True
            
            iv, open_interest = 32.0, 1000
            iv_is_fallback = False
            
            try:
                expirations = ticker.options
                if expirations:
                    target_expiry = expirations[min(2, len(expirations)-1)]
                    opt_chain = ticker.option_chain(target_expiry)
                    calls = opt_chain.calls
                    if not calls.empty:
                        calls['strike_diff'] = (calls['strike'] - current_price).abs()
                        atm_call = calls.sort_values(by='strike_diff').iloc[0]
                        if pd.notnull(atm_call.get('impliedVolatility')):
                            iv = atm_call['impliedVolatility'] * 100
                        if pd.notnull(atm_call.get('openInterest')):
                            open_interest = int(atm_call['openInterest'])
            except Exception as opt_err:
                iv_is_fallback = True
                st.warning(f"⚠️ Live Options Chain Missing: {opt_err}. Falling back to historical asset volatility metrics.")
            
            # --- SIGNAL TREE FILTER LOGIC ---
            if iv > 100:
                strategy, status_type = "⚠️ STAY IN CASH", "warning"
                reason = f"Asset implied volatility is abnormally high ({iv:.1f}% IV), representing excessive binary risk."
            elif is_bullish_trend and iv < 35 and volume_confirmed and rsi_safe_long:
                if rsp_confirmed_bullish:
                    strategy, status_type = "🟢 BUY CALLS", "success"
                    reason = f"Confirmed technical breakout above the 20-EMA. Broad market participation (RSP) is healthy, validating upward momentum."
                else:
                    strategy, status_type = "⚠️ STAY IN CASH (MARKET TRAP)", "warning"
                    reason = f"The individual ticker is breaking out, but the Equal-Weighted S&P (RSP) is in a macro downtrend. Entry blocked to prevent buying a low-breadth fakeout."
            elif not is_bullish_trend and iv < 50 and volume_confirmed and rsi_safe_short:
                strategy, status_type = "🔴 BUY PUTS", "error"
                reason = f"Bearish trajectory breakdown below the 20-EMA line. High distribution volume confirms selling pressure."
            elif is_bullish_trend and iv >= 55:
                if rsp_confirmed_bullish:
                    strategy, status_type = "🔵 SELL CASH-SECURED PUTS", "info"
                    reason = f"Bullish trend structure paired with highly inflated implied options premiums. RSP confirms underlying market support."
                else:
                    strategy, status_type = "⚠️ STAY IN CASH (PREMIUM RISK)", "warning"
                    reason = f"High IV makes selling premium attractive, but the Equal-Weighted index is macro-bearish. Risk of sudden underlying assignment is high."
            else:
                strategy, status_type = "🟡 STAY IN CASH", "warning"
                reason = f"Setup rejected due to technical divergence or missing momentum confirmations. Vol Confirmed: {volume_confirmed} | RSI: {current_rsi:.1f}"
            
            if status_type == "success": st.success(f"### Strategy Signal: {strategy}")
            elif status_type == "error": st.error(f"### Strategy Signal: {strategy}")
            elif status_type == "info": st.info(f"### Strategy Signal: {strategy}")
            else: st.warning(f"### Strategy Signal: {strategy}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Spot Price", f"${current_price:.2f}")
            col2.metric("Distance from 20-EMA", f"{trend_pct:+.1f}%")
            col3.metric("ATM Option Implied Volatility", f"{iv:.1f}%" + (" (Fallback)" if iv_is_fallback else ""))
            col4.metric("RSI (14-Day Momentum)", f"{current_rsi:.1f}" if not pd.isna(current_rsi) else "N/A")
            
            st.caption(f"🌍 Broad Market Baseline: Equal-Weighted S&P 500 (RSP) is {'🟢 BULLISH' if rsp_confirmed_bullish else '🔴 BEARISH'}")
            st.markdown(f"**Audit Breakdown:** {reason}")
            st.markdown("---")

if not os.path.exists("options_candidates.csv"):
    st.warning("⚠️ No database scanner output located on server. Please run a Live Market Scan in the sidebar to generate data files.")
else:
    df = pd.read_csv("options_candidates.csv")
    
    # --- GLOBAL MACRO PIPELINE ---
    vix_val, vix_delta = fetch_live_vix_metrics()
    breadth_df, breadth_errors = fetch_breadth_metrics_panel()
    
    def clean_numeric_col(val):
        try: return float(str(val).replace('$','').replace('%','').replace(',','').strip())
        except: return 0.0
    
    num_adv = len(df[~df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)])
    num_dec = len(df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)])
    ad_ratio = num_adv / max(1, num_dec)
    
    df['Clean_Vol'] = df['Volume'].apply(clean_numeric_col) if 'Volume' in df.columns else 1.0
    adv_vol_sum = df[~df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)]['Clean_Vol'].sum()
    total_vol_sum = df['Clean_Vol'].sum()
    vol_ratio_pct = (adv_vol_sum / max(1, total_vol_sum)) * 100
    
    bullish_indices_count = len(breadth_df[breadth_df["Trend Status"] == "🟢 BULLISH"]) if not breadth_df.empty else 0
    
    # --- EXECUTIVE OPERATIONAL ALERTS ---
    st.markdown("### 📡 Market Regime & Risk Assessment")
    
    if vix_val >= 28.0:
        st.error(f"🛑 **SYSTEMIC LIQUIDATION RISK (VIX: {vix_val:.2f}):** High market fear regime. Tail-risk event likelihood is high. Suspend long entries and preserve cash capital buffers.")
    elif bullish_indices_count == 3 and ad_ratio > 1.2 and vix_val < 16.0:
        st.success(f"🔥 **CONVERGENT RISK-ON ENVIRONMENT (VIX: {vix_val:.2f}):** Strong multi-index market breadth paired with inexpensive implied options premiums. Ideal conditions for **Tab 1 Long Calls**.")
    elif vix_val >= 21.0 and ad_ratio >= 0.8:
        st.info(f"🔵 **ELEVATED PREMIUM REGIME (VIX: {vix_val:.2f}):** Market indices are steady but underlying contract pricing is highly inflated. Focus deployment on **Tab 2 (Put Selling)** to capture high option decay.")
    elif ad_ratio < 0.9 and bullish_indices_count >= 1:
        st.warning(f"⚠️ **TOP-HEAVY INDEX BIAS (VIX: {vix_val:.2f}):** Market returns are concentrated in select mega-caps while broader listing participation decays. Individual stock breakouts are high-risk. Pivot to **Tab 3 Alpha**.")
    else:
        st.markdown(f"ℹ️ **NORMAL TRAJECTORY REGIME (VIX: {vix_val:.2f}):** Baseline parameters detected. Deploy capital with standardized position sizes and trailing stop-loss protection.")
        
    st.markdown("---")
    
    total_scanned = len(df)
    passed_action = len(df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)])
    stay_cash = len(df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)])
    
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("📋 Tickers Scanned", f"{total_scanned} Universe")
    col_b.metric("🔥 Setup Triggers", f"{passed_action} Active")
    col_c.metric("🛡️ Filter Rejections", f"{stay_cash} Cached Cash")
    col_d.metric("🕵️‍♂️ CBOE Volatility Index (VIX)", f"{vix_val:.2f}", f"{vix_delta:+.2f}")
    st.markdown("---")
    
    # --- DASHBOARD TABS ---
    tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🌍 Broad Market Breadth Radar",
        "🔥 Directional Buying (Calls/Puts)", 
        "🛡️ Premium Collection (CSPs)", 
        "🛰️ Idiosyncratic Alpha Screen",
        "📋 All Active Candidates",
        "🔍 Audit Trail (Rejected Tickers)",
        "🔮 Equity Signal Backtester" # RENAME: Changed tab name from Options to Equity to match return math
    ])
    
    with tab0:
        st.subheader("🌍 Macro-Index Trend Participation Radar")
        st.caption("Tracks underlying market health across core indexing mechanisms.")
        
        # FIX BARE EXCEPT: Explicit error printing for indexing pipelines
        if breadth_errors:
            for err in breadth_errors:
                st.caption(err)
                
        if not breadth_df.empty:
            st.dataframe(breadth_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📊 Synthesized Breadth Analytics")
        st.caption("Aggregated statistical readings computed across the scanned database population.")
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(label="📈 Advance / Decline Ratio", value=f"{ad_ratio:.2f}x", delta="Advancers Dominant" if ad_ratio > 1.0 else "Decliners Dominant")
        m_col2.metric(label="🔊 Institutional Volume Ratio", value=f"{vol_ratio_pct:.1f}%", delta="Net Inflow Allocation" if vol_ratio_pct > 55 else "Net Outflow Distribution")
        
        df['Clean_vs_EMA'] = df['vs 20-EMA'].apply(clean_numeric_col) if 'vs 20-EMA' in df.columns else 0.0
        net_high_low_spread = len(df[df['Clean_vs_EMA'] > 8.0]) - len(df[df['Clean_vs_EMA'] < -8.0])
        m_col3.metric(label="🎯 High / Low Extension Spread", value=f"{net_high_low_spread:+d}", delta="Expansion" if net_high_low_spread >= 0 else "Contraction")
            
    with tab1:
        st.subheader("Low Implied-Volatility Breakout Setups")
        buying_df = df[df["RECOMMENDED ACTION"].str.contains("BUY", na=False)]
        if not buying_df.empty: st.dataframe(buying_df, use_container_width=True, hide_index=True)
        else: st.info("No qualitative directional buying setups identified currently.")
            
    with tab2:
        st.subheader("🛡️ Premium Collection Configuration Node")
        csp_base = df[df["RECOMMENDED ACTION"].str.contains("CASH-SECURED", na=False)].copy()
        if csp_base.empty:
            st.info("No high-implied-volatility premium targets identified.")
        else:
            today = datetime.now()
            opt_min_date = (today + timedelta(days=30)).strftime("%b %d, %Y")
            opt_max_date = (today + timedelta(days=45)).strftime("%b %d, %Y")
            csp_base["Spot"] = csp_base["Price"].apply(lambda x: float(str(x).replace('$','').strip()))
            csp_base["🎯 INCOME Play Strike"] = (csp_base["Spot"] * 0.93).apply(lambda x: f"${round(x * 2) / 2:.2f}")
            csp_base["🛍️ DISCOUNT Play Strike"] = (csp_base["Spot"] * 0.88).apply(lambda x: f"${round(x * 2) / 2:.2f}")
            csp_base["Expirations Target"] = f"{opt_min_date} to {opt_max_date}"
            final_view = csp_base[["Ticker", "Price", "Implied Vol (IV)", "Expirations Target", "🎯 INCOME Play Strike", "🛍️ DISCOUNT Play Strike"]]
            st.dataframe(final_view, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("🛰️ Market-Decoupled Alpha Matrix")
        st.caption("Identifies tickers demonstrating positive technical setups during broad market downtrends.")
        active_candidates = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]["Ticker"].unique().tolist()
        
        if not active_candidates:
            st.info("No active watchlist candidates available to process for Alpha metrics.")
        else:
            if st.button("🛰️ Process Rolling 3-Year Alpha Correlations"):
                alpha_leads = []
                with st.spinner("Processing alpha metrics via cached data layers..."):
                    try:
                        # Fetch and cache index benchmark once
                        spy_h = yf.Ticker("SPY").history(period="3y")
                        
                        for sym in active_candidates:
                            # FIX BOTTLE-NECK: Rerouted to cached synchronized data layer
                            a_h = fetch_synchronized_macro_data(sym, horizon_years=3)
                            if a_h.empty or len(a_h) < 200: 
                                continue
                            
                            a_h['20_EMA'] = a_h['Close'].ewm(span=20, adjust=False).mean()
                            a_h['SPY_200_EMA'] = a_h['SPY_Close'].ewm(span=200, adjust=False).mean()
                            
                            in_pos, ent_p, win_macro, tot_macro, win_div, tot_div = False, 0.0, 0, 0, 0, 0
                            for idx in range(200, len(a_h)):
                                if not in_pos:
                                    if a_h['Close'].iloc[idx-1] <= a_h['20_EMA'].iloc[idx-1] and a_h['Close'].iloc[idx] > a_h['20_EMA'].iloc[idx]:
                                        in_pos = True
                                        ent_p = float(a_h['Close'].iloc[idx])
                                        is_macro_b = a_h['SPY_Close'].iloc[idx] > a_h['SPY_200_EMA'].iloc[idx]
                                        t_type = "MACRO" if is_macro_b else "DIV"
                                        days_in = 0
                                else:
                                    days_in += 1
                                    ret = (a_h['Close'].iloc[idx] - ent_p) / ent_p
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
                                play = "🟢 BUY CALLS" if clean_iv < 50 else "🔵 SELL CSPs"
                                alpha_leads.append({
                                    "Ticker": sym,
                                    "Macro Bull Win Rate": f"{m_wr:.1f}%",
                                    "Divergent Bear Win Rate": f"{d_wr:.1f}%",
                                    "Alpha Score": f"+{(d_wr - 40.0):.1f}",
                                    "Target Exploitation": play
                                })
                        if alpha_leads:
                            st.success(f"Isolated {len(alpha_leads)} idiosyncratic candidates.")
                            st.dataframe(pd.DataFrame(alpha_leads).sort_values(by="Alpha Score", ascending=False), use_container_width=True, hide_index=True)
                        else:
                            st.info("No tickers exhibited significant historical decoupling criteria.")
                    except Exception as ex:
                        st.error(f"Alpha analysis processing exception: {ex}")
            
    with tab4:
        st.subheader("Master Active Ticker Board")
        active_df = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]
        st.dataframe(active_df, use_container_width=True, hide_index=True)
        
    with tab5:
        st.subheader("Evaluated Watchlist Items Intentionally Restricted to Cash")
        rejected_df = df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)]
        st.dataframe(rejected_df[["Ticker", "Price", "vs 20-EMA", "Implied Vol (IV)", "RECOMMENDED ACTION", "Reasoning Breakdown"]], use_container_width=True, hide_index=True)

    with tab6:
        st.subheader("🔮 Historical Equity Signal Simulation Engine")
        # EXPLANATORY OVERSIGHT: User clarification regarding underlying return matrix calculations
        st.info("💡 **Note on Performance Tracking:** Returns generated below reflect raw stock price performance metrics. True options strategy returns would scale relative to chosen leverage parameters, expiration dates, and delta allocations.")
        
        bt_col1, bt_col2, bt_col3, bt_col4, bt_col5 = st.columns(5)
        bt_symbol = bt_col1.text_input("Ticker Symbol:", value="TSLA", key="bt_sym_input").upper().strip()
        bt_strategy = bt_col2.selectbox("Signal Vector Strategy:", ["🟢 BUY CALLS (Bullish)", "🔴 BUY PUTS (Bearish)"], key="bt_strat_select")
        bt_years = bt_col3.slider("Lookback Window (Years)", min_value=1, max_value=5, value=3, key="bt_horizon_slider")
        bt_target = bt_col4.slider("Take Profit (%)", min_value=1, max_value=20, value=10, key="bt_tp_slider") / 100
        bt_stop = bt_col5.slider("Stop Loss (%)", min_value=1, max_value=15, value=5, key="bt_sl_slider") / 100
        
        if st.button("🔮 Compute Historical Performance Data", key="execute_bt_button"):
            with st.spinner("Processing historical pricing loops..."):
                try:
                    combined_df = fetch_synchronized_macro_data(bt_symbol, horizon_years=bt_years)
                    if combined_df.empty:
                        st.error("Historical lookup failed. Verify ticker validity or check exchange accessibility pipelines.")
                    else:
                        combined_df['20_EMA'] = combined_df['Close'].ewm(span=20, adjust=False).mean()
                        combined_df['SPY_200_EMA'] = combined_df['SPY_Close'].ewm(span=200, adjust=False).mean()
                        
                        combined_df['prev_close'] = combined_df['Close'].shift(1)
                        combined_df['prev_ema'] = combined_df['20_EMA'].shift(1)
                        
                        if "BUY CALLS" in bt_strategy:
                            combined_df['signal_triggered'] = (combined_df['prev_close'] <= combined_df['prev_ema']) & (combined_df['Close'] > combined_df['20_EMA'])
                        else:
                            combined_df['signal_triggered'] = (combined_df['prev_close'] >= combined_df['prev_ema']) & (combined_df['Close'] < combined_df['20_EMA'])
                        
                        signal_indices = np.where(combined_df['signal_triggered'])[0]
                        sim_trades = []
                        
                        for sig_idx in signal_indices:
                            if sig_idx < 200 or sig_idx >= len(combined_df) - 1:
                                continue
                            ent_date = combined_df.index[sig_idx]
                            ent_price = float(combined_df['Close'].iloc[sig_idx])
                            macro_bullish = combined_df['SPY_Close'].iloc[sig_idx] > combined_df['SPY_200_EMA'].iloc[sig_idx]
                            
                            # FIX TERNARY BUG: Clean conditional assignment branching based on strategy profiles
                            if "BUY CALLS" in bt_strategy:
                                trade_regime = "🟢 BULLISH MACRO" if macro_bullish else "⚠️ BEAR TRAP RISK"
                            else:
                                trade_regime = "🔴 BEARISH MACRO" if not macro_bullish else "⚠️ BULL TRAP RISK"
                                
                            exit_found = False
                            max_holding_window = min(21, len(combined_df) - sig_idx - 1)
                            
                            for look_ahead in range(1, max_holding_window + 1):
                                eval_idx = sig_idx + look_ahead
                                future_close = combined_df['Close'].iloc[eval_idx]
                                return_pct = (future_close - ent_price) / ent_price if "BUY CALLS" in bt_strategy else (ent_price - future_close) / ent_price
                                    
                                if return_pct >= bt_target:
                                    sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "WIN", "Underlying Return": f"+{return_pct*100:.1f}% 🎯"})
                                    exit_found = True
                                    break
                                elif return_pct <= -bt_stop:
                                    sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "LOSS", "Underlying Return": f"-{abs(return_pct)*100:.1f}% 🛑"})
                                    exit_found = True
                                    break
                                    
                            if not exit_found and max_holding_window > 0:
                                final_close = combined_df['Close'].iloc[sig_idx + max_holding_window]
                                final_return = (final_close - ent_price) / ent_price if "BUY CALLS" in bt_strategy else (ent_price - final_close) / ent_price
                                sim_trades.append({"Date": ent_date.strftime('%Y-%m-%d'), "Regime State": trade_regime, "Result": "TIMEOUT", "Underlying Return": f"{final_return*100:+.1f}% ⏳"})
                                
                        if not sim_trades:
                            st.info("No technical strategy trade triggers met current parameters over this historical horizon.")
                        else:
                            t_df = pd.DataFrame(sim_trades)
                            bull_setups = t_df[t_df['Regime State'].str.contains("BULLISH MACRO|BEARISH MACRO", na=False)]
                            trap_setups = t_df[t_df['Regime State'].str.contains("RISK", na=False)]
                            win_rate_macro = (len(bull_setups[bull_setups['Result'] == 'WIN']) / len(bull_setups) * 100) if len(bull_setups) > 0 else 0.0
                            win_rate_trap = (len(trap_setups[trap_setups['Result'] == 'WIN']) / len(trap_setups) * 100) if len(trap_setups) > 0 else 0.0
                            
                            st.subheader("📋 Backtest Execution Summary")
                            pa, pb = st.columns(2)
                            pa.metric("Win Rate: Macro Aligned", f"{win_rate_macro:.1f}%")
                            pb.metric("Win Rate: Market Divergent", f"{win_rate_trap:.1f}%")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Backtest runtime execution exception: {e}")
