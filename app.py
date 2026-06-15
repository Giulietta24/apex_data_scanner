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
        # FIXED: Only cache the historical DataFrame array to avoid UnserializableReturnValueError
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

# Anti-Rate Limiting UX Guard Form
with st.sidebar.form(key="single_ticker_form"):
    custom_symbol_input = st.text_input("Type stock symbol (e.g., TSLA, PLTR, RKLB):").upper().strip()
    submit_audit = st.form_submit_button(label="🚀 Execute Audit")

# --- MAIN DASHBOARD INTERFACE ---
if submit_audit and custom_symbol_input:
    st.subheader(f"⚡ Instant On-Demand Audit for: {custom_symbol_input}")
    with st.spinner(f"Querying encrypted arrays for {custom_symbol_input}..."):
        # FIXED: Pull data array via cache, build live tracker object purely inside local runtime
        hist = fetch_ticker_data_cached(custom_symbol_input, period="3mo")
        ticker = yf.Ticker(custom_symbol_input)
        
        # Pull global broad-market health filters (RSP Index)
        rsp_confirmed_bullish, current_rsp_price = fetch_rsp_market_health()
        
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
                st.warning(f"⚠️ Options Data Pipeline Interrupted: {opt_err}. Utilizing static volatility fallback math model.")
            
            # --- MULTI-DIMENSIONAL LOGIC DECISION TREE MATRIX ---
            if iv > 100:
                strategy, status_type = "⚠️ STAY IN CASH", "warning"
                reason = f"Asset sitting inside extreme volatility crash hazard zone ({iv:.1f}% IV)."
            
            # BUY CALLS Execution Pipeline
            elif is_bullish_trend and iv < 35 and volume_confirmed and rsi_safe_long:
                if rsp_confirmed_bullish:
                    strategy, status_type = "🟢 BUY CALLS", "success"
                    reason = f"Confirmed technical breakout above 20-EMA. Broad market participation (RSP) is healthy, giving this setup maximum wind at its back."
                else:
                    strategy, status_type = "⚠️ STAY IN CASH (MARKET TRAP)", "warning"
                    reason = f"Ticker is breaking out, but Equal-Weighted S&P (RSP) is in a downtrend. Setup blocked to prevent buying a fake liquidity trap."
            
            # BUY PUTS Execution Pipeline
            elif not is_bullish_trend and iv < 50 and volume_confirmed and rsi_safe_short:
                strategy, status_type = "🔴 BUY PUTS", "error"
                reason = f"Bearish trajectory breakdown below support line. High distribution volume confirms institutional liquidation pressure."
            
            # SELL CASH-SECURED PUTS Execution Pipeline
            elif is_bullish_trend and iv >= 55:
                if rsp_confirmed_bullish:
                    strategy, status_type = "🔵 SELL CASH-SECURED PUTS", "info"
                    reason = f"Bullish trend framework combined with highly inflated implied premiums. RSP confirms underlying market structure is supportive."
                else:
                    strategy, status_type = "⚠️ STAY IN CASH (PREMIUM RISK)", "warning"
                    reason = f"High IV makes selling credits tempting, but Equal-Weighted broad market (RSP) is weak. High risk of getting heavily assigned on a market flush."
            
            else:
                strategy, status_type = "🟡 STAY IN CASH", "warning"
                reason = f"Setup rejected due to divergence or failing technical confirmations. Volume confirmed: {volume_confirmed} | RSI Check: {current_rsi:.1f}"
