# data_worker.py
import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from signals import evaluate_signal

# Separate lists based on underlying asset characteristics 
EQUITY_UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "PLTR", "AMD", "NFLX", "MARA", "COIN", "RKLB"]
ETF_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA"]

def calculate_rsi(series, periods=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))

def process_universe_pool(ticker_list, is_etf, rsp_bullish):
    results = []
    
    for symbol in ticker_list:
        print(f"📡 Auditing {symbol}...")
        try:
            # Enforce defensive pacing to eliminate provider rate-limiting
            time.sleep(0.5)
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")
            
            # --- CRITICAL PROTECTION LAYER: NO MOCK DATA INJECTIONS ---
            if hist.empty or len(hist) < 20:
                print(f"⚠️ {symbol}: Incomplete data array returned from provider. Hard skipping ticker.")
                continue
                
            # Compute underlying math
            current_price = hist['Close'].iloc[-1]
            hist['20_EMA'] = hist['Close'].ewm(span=20, adjust=False).mean()
            hist['Vol_MA20'] = hist['Volume'].rolling(window=20).mean()
            hist['RSI_14'] = calculate_rsi(hist['Close'])
            
            current_ema = hist['20_EMA'].iloc[-1]
            current_vol = hist['Volume'].iloc[-1]
            avg_vol = hist['Vol_MA20'].iloc[-1]
            current_rsi = hist['RSI_14'].iloc[-1]
            
            is_bullish_trend = current_price > current_ema
            volume_confirmed = current_vol > avg_vol
            trend_pct = ((current_price - current_ema) / current_ema) * 100
            
            # Options defaults
            iv = 25.0 if is_etf else 45.0  # Context-aware standard default baselines
            spread_pct = 0.50
            iv_source = "DEFAULT_BASE"
            
            # Process options contracts safely
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
                            iv_source = "LIVE_CHAIN"
                            
                        # DYNAMIC SPREAD CALCULATION: Replacing hardcoded 0.4% baseline
                        bid = atm_call.get('bid')
                        ask = atm_call.get('ask')
                        if pd.notnull(bid) and pd.notnull(ask) and ask > 0:
                            spread_pct = ((ask - bid) / ask) * 100
            except Exception as opt_err:
                print(f"⚠️ {symbol} Options Chain Failure: {opt_err}. Engaging default risk framework.")
                iv_source = "FALLBACK_PROTECTED"

            # Execute cross-imported signal computation matrix
            strategy, reason = evaluate_signal(is_bullish_trend, iv, volume_confirmed, current_rsi, rsp_bullish)
            
            results.append({
                "Ticker": symbol,
                "Price": f"${current_price:.2f}",
                "vs 20-EMA": f"{trend_pct:+.2f}%",
                "Implied Vol (IV)": f"{iv:.1f}%",
                "ATM Bid-Ask Spread": f"{spread_pct:.2f}%",
                "Volume": f"{current_vol:,}",
                "RECOMMENDED ACTION": strategy,
                "Reasoning Breakdown": reason,
                "Asset Class": "ETF" if is_etf else "EQUITY",
                "IV Data Quality": iv_source
            })
            
        except Exception as ticker_err:
            print(f"❌ Severe processing exception on global ticker component {symbol}: {ticker_err}")
            continue
            
    return results

def scan_market():
    print("🚀 Initiating System Scan Profile...")
    
    # Calculate Broad Market Equal-Weighted Breadth Baseline
    rsp_bullish = True
    try:
        rsp = yf.Ticker("RSP").history(period="3mo")
        if not rsp.empty and len(rsp) >= 20:
            rsp['20_EMA'] = rsp['Close'].ewm(span=20, adjust=False).mean()
            rsp_bullish = rsp['Close'].iloc[-1] > rsp['20_EMA'].iloc[-1]
    except Exception as e:
        print(f"⚠️ RSP Breadth engine lookup failed: {e}. Defaulting broad market matrix to neutral settings.")

    # Process individual asset universes separately 
    equity_results = process_universe_pool(EQUITY_UNIVERSE, is_etf=False, rsp_bullish=rsp_bullish)
    etf_results = process_universe_pool(ETF_UNIVERSE, is_etf=True, rsp_bullish=rsp_bullish)
    
    master_results = equity_results + etf_results
    
    if master_results:
        df = pd.DataFrame(master_results)
        df.to_csv("options_candidates.csv", index=False)
        print(f"✅ Database Export Matrix Updated Successfully with {len(df)} Live Audited Records.")
    else:
        print("🛑 Scan completed with zero viable output datasets. File export bypassed to avoid bricking cache layers.")

if __name__ == "__main__":
    scan_market()
