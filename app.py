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

# --- PERFORMANCE LAYER CACHING CORE ---
@st.cache_data(ttl=300)
def fetch_ticker_data_cached(symbol, period="3mo"):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        return hist, ticker
    except Exception as e:
        return pd.DataFrame(), None

@st.cache_data(ttl=300)
def fetch_synchronized_macro_data(symbol, horizon_years=3):
    try:
        asset_h = yf.Ticker(symbol).history(period=f"{horizon_years}y")
        spy_h = yf.Ticker("SPY").history(period=f"{horizon_years}y")
        if asset_h.empty or spy_h.empty:
            return pd.DataFrame()
        combined = asset_h.join(spy_h['Close'].rename('SPY_Close'), how='inner')
        return combined
    except:
        return pd.DataFrame()

# --- MATHEMATICAL MOMENTUM INDICATORS ---
def calculate_rsi(series, periods=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

# --- SIDEBAR CONTROLS & SECURITY GUARDS ---
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

# PATCH: Wrap with an explicit Streamlit Form block to handle debouncing and prevent character rate-limiting
with st.sidebar.form(key="single_ticker_form"):
    custom_symbol_input = st.text_input("Type stock symbol (e.g., TSLA, PLTR, RKLB):").upper().strip()
    submit_audit = st.form_submit_button(label="🚀 Execute Audit")

# --- MAIN DASHBOARD INTERFACE ---
if submit_audit and custom_symbol_input:
    st.subheader(f"⚡ Instant On-Demand Audit for: {custom_symbol_input}")
    with st.spinner(f"Querying encrypted arrays for {custom_symbol_input}..."):
        hist, ticker = fetch_ticker_data_cached(custom_symbol_input, period="3mo")
        
        if hist.empty or len(hist) < 20:
            st.error(f"Could not retrieve sufficient trading data arrays for '{custom_symbol_input}'.")
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
            
            # Quantitative Filters Architecture Confirmation
            is_bullish_trend = current_price > current_ema
            volume_confirmed = current_vol > avg_vol
            rsi_safe_long = current_rsi < 75 if not pd.isna(current_rsi) else True
            rsi_safe_short = current_rsi > 30 if not pd.isna(current_rsi) else True
            
            iv, open_interest = 32.0, 1000
            iv_is_fallback = False
            
            # PATCH: Purged blind execution loop pass. Surfaced option tracking metrics natively.
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
                st.amber_warning_banner = st.warning(f"⚠️ Options Data Pipeline Interrupted: {opt_err}. Utilizing static volatility fallback math model.")
            
            # Multi-Dimensional Logic Decision Tree
            if iv > 100:
                strategy, status_type = "⚠️ STAY IN CASH", "warning"
                reason = f"Asset sitting inside extreme volatility crash hazard zone ({iv:.1f}% IV)."
            elif is_bullish_trend and iv < 35 and volume_confirmed and rsi_safe_long:
                strategy, status_type = "🟢 BUY CALLS", "success"
                reason = f"Confirmed technical breakout above 20-EMA backed by high volume activity. Momentum RSI ({current_rsi:.1f}) holds strong extension headroom."
            elif not is_bullish_trend and iv < 50 and volume_confirmed and rsi_safe_short:
                strategy, status_type = "🔴 BUY PUTS", "error"
                reason = f"Bearish trajectory breakdown below support line. High distribution volume confirms institutional liquidation pressure."
            elif is_bullish_trend and iv >= 55:
                strategy, status_type = "🔵 SELL CASH-SECURED PUTS", "info"
                reason = f"Bullish trend framework combined with highly inflated implied premiums. Optimal setup for selling decay credits."
            else:
                strategy, status_type = "🟡 STAY IN CASH", "warning"
                reason = f"Setup rejected due to divergence or failing technical confirmations. Volume confirmed: {volume_confirmed} | RSI Check: {current_rsi:.1f}"
            
            if status_type == "success": st.success(f"### Strategy Signal: {strategy}")
            elif status_type == "error": st.error(f"### Strategy Signal: {strategy}")
            elif status_type == "info": st.info(f"### Strategy Signal: {strategy}")
            else: st.warning(f"### Strategy Signal: {strategy}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Spot Price", f"${current_price:.2f}")
            col2.metric("Distance from 20-EMA", f"{trend_pct:+.1f}%")
            col3.metric("ATM Option Implied Volatility", f"{iv:.1f}%" + (" (Fallback)" if iv_is_fallback else ""))
            col4.metric("RSI (14-Day Momentum)", f"{current_rsi:.1f}" if not pd.isna(current_rsi) else "N/A")
            st.markdown(f"**Structural Audit Execution Analysis:** {reason}")
            st.markdown("---")

if not os.path.exists("options_candidates.csv"):
    st.warning("⚠️ No active options screening matrix located on server. Please execute broad scan initialization via sidebar configuration layout.")
else:
    df = pd.read_csv("options_candidates.csv")
    
    total_scanned = len(df)
    passed_action = len(df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)])
    stay_cash = len(df[df["RECOMMENDED ACTION"].str.contains("STAY IN CASH", na=False)])
    
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
        st.caption("Scans active candidates using real-time sync to pinpoint tickers whose setups survive independent of S&P 500 market risk.")
        
        active_candidates = df[df["RECOMMENDED ACTION"].str.contains("BUY|CASH-SECURED", na=False)]["Ticker"].unique().tolist()
        
        if not active_candidates:
            st.info("No active candidates currently available to screen for Alpha.")
        else:
            if st.button("🛰️ Extract Market-Decoupled Alpha"):
                alpha_leads = []
                with st.spinner("Processing decoupled alpha correlation arrays..."):
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
                            st.success(f"🎯 Isolated {len(alpha_leads)} Idiosyncratic Alpha Engines!")
                            st.dataframe(pd.DataFrame(alpha_leads).sort_values(by="Alpha Score", ascending=False), use_container_width=True, hide_index=True)
                    except Exception as ex:
                        st.error(f"Alpha Matrix Interrupted: {ex}")
            
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
        st.caption("Filters historical setups through Macro Regimes to calculate mathematical underlying stock outcomes.")
        
        # User Controls Configuration
        bt_col1, bt_col2, bt_col3, bt_col4, bt_col5 = st.columns(5)
        bt_symbol = bt_col1.text_input("Ticker to Predict:", value="TSLA", key="bt_sym_input").upper().strip()
        bt_strategy = bt_col2.selectbox("Option Flow Type:", ["🟢 BUY CALLS (Bullish)", "🔴 BUY PUTS (Bearish)"], key="bt_strat_select")
        bt_years = bt_col3.slider("Backtest Lookback Horizon (Years)", min_value=1, max_value=5, value=3, key="bt_horizon_slider")
        bt_target = bt_col4.slider("Take Profit (%)", min_value=1, max_value=20, value=10, key="bt_tp_slider") / 100
        bt_stop = bt_col5.slider("Stop Loss (%)", min_value=1, max_value=15, value=5, key="bt_sl_slider") / 100
        
        if st.button("🔮 Calculate Predictive Probability Matrix", key="execute_bt_button"):
            with st.spinner("Executing optimized vectorized computation matrices..."):
                try:
                    combined_df = fetch_synchronized_macro_data(bt_symbol, horizon_years=bt_years)
                    
                    if combined_df.empty:
                        st.error("Missing historical sequence alignment maps. Verification execution failed.")
                    else:
                        combined_df['20_EMA'] = combined_df['Close'].ewm(span=20, adjust=False).mean()
                        combined_df['SPY_200_EMA'] = combined_df['SPY_Close'].ewm(span=200, adjust=False).mean()
                        
                        # PATCH: Fully vectorized shift logic execution to eliminate standard loop overhead delays
                        combined_df['prev_close'] = combined_df['Close'].shift(1)
                        combined_df['prev_ema'] = combined_df['20_EMA'].shift(1)
                        
                        if "BUY CALLS" in bt_strategy:
                            combined_df['signal_triggered'] = (combined_df['prev_close'] <= combined_df['prev_ema']) & (combined_df['Close'] > combined_df['20_EMA'])
                        else:
                            combined_df['signal_triggered'] = (combined_df['prev_close'] >= combined_df['prev_ema']) & (combined_df['Close'] < combined_df['20_EMA'])
                        
                        signal_indices = np.where(combined_df['signal_triggered'])[0]
                        sim_trades = []
                        
                        # Process metrics parsing only along filtered signal date indexes
                        for sig_idx in signal_indices:
                            if sig_idx < 200 or sig_idx >= len(combined_df) - 1:
                                continue
                                
                            ent_date = combined_df.index[sig_idx]
                            ent_price = float(combined_df['Close'].iloc[sig_idx])
                            macro_bullish = combined_df['SPY_Close'].iloc[sig_idx] > combined_df['SPY_200_EMA'].iloc[sig_idx]
                            
                            if "BUY CALLS" in bt_strategy:
                                trade_regime = "🟢 BULLISH MACRO" if macro_bullish else "⚠️ BEAR TRAP RISK"
                            else:
                                trade_regime = "🔴 BEARISH MACRO" if not macro_bullish else "⚠️ BULL TRAP RISK"
                                
                            # Track forward price path boundaries up to holding cap
                            exit_found = False
                            max_holding_window = min(21, len(combined_df) - sig_idx - 1)
                            
                            for look_ahead in range(1, max_holding_window + 1):
                                eval_idx = sig_idx + look_ahead
                                future_close = combined_df['Close'].iloc[eval_idx]
                                future_date = combined_df.index[eval_idx]
                                
                                if "BUY PUTS" in bt_strategy:
                                    return_pct = (ent_price - future_close) / ent_price
                                else:
                                    return_pct = (future_close - ent_price) / ent_price
                                    
                                if return_pct >= bt_target:
                                    sim_trades.append({
                                        "Date": ent_date.strftime('%Y-%m-%d'),
                                        "Regime State": trade_regime,
                                        "Result": "WIN",
                                        "Asset Return": f"+{return_pct*100:.1f}% 🎯"
                                    })
                                    exit_found = True
                                    break
                                elif return_pct <= -bt_stop:
                                    sim_trades.append({
                                        "Date": ent_date.strftime('%Y-%m-%d'),
                                        "Regime State": trade_regime,
                                        "Result": "LOSS",
                                        "Asset Return": f"-{abs(return_pct)*100:.1f}% 🛑"
                                    })
                                    exit_found = True
                                    break
                                    
                            if not exit_found and max_holding_window > 0:
                                final_idx = sig_idx + max_holding_window
                                final_close = combined_df['Close'].iloc[final_idx]
                                if "BUY PUTS" in bt_strategy:
                                    final_return = (ent_price - final_close) / ent_price
                                else:
                                    final_return = (final_close - ent_price) / ent_price
                                    
                                sim_trades.append({
                                    "Date": ent_date.strftime('%Y-%m-%d'),
                                    "Regime State": trade_regime,
                                    "Result": "TIMEOUT",
                                    "Asset Return": f"{final_return*100:+.1f}% ⏳"
                                })
                                
                        if not sim_trades:
                            st.info("No localized strategy setups triggered within the designated parameters.")
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
                            
                            # PATCH: Swapped simulated options returns for direct underlying asset delta metrics
                            st.markdown("### Verifiable Historical Asset Metrics Ledger")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                            
                except Exception as e:
                    st.error(f"Probability Engine Interrupted: {e}")
