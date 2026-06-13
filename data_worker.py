# data_worker.py
import yfinance as yf
import pandas as pd
import numpy as np

def get_market_universe():
    """Automatically grabs tickers from Large-Cap and Mid-Cap market indices via Wikipedia"""
    print("🌐 Dynamically fetching market indexes from the web...")
    # Seed with high-volume, cross-cap ETFs
    tickers = set(["SPY", "QQQ", "IWM", "DIA"]) 
    
    try:
        # 1. Pull S&P 500 (Large Cap Universe)
        sp500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers.update(sp500['Symbol'].dropna().tolist())
        
        # 2. Pull S&P MidCap 400 (Mid Cap & Liquid Small-Cap High Beta Universe)
        sp400 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")[0]
        tickers.update(sp400['Ticker symbol'].dropna().tolist())
        
        # Clean up ticker symbols for Yahoo Finance format compatibility
        cleaned_tickers = [str(t).replace('.', '-').replace('/', '-').strip() for t in tickers]
        print(f"📊 Market Universe Loaded: Found {len(cleaned_tickers)} total candidates to audit.")
        return cleaned_tickers
    except Exception as e:
        print(f"⚠️ Error fetching live index data: {e}. Utilizing high-liquidity fallback list.")
        return ["SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMD", "PLTR", "COIN", "MARA", "RIVN"]

def scan_market():
    ticker_universe = get_market_universe()
    results = []
    
    print("🚀 Initiating Multi-Stage Liquidity Filter Flow...")
    
    for symbol in ticker_universe:
        try:
            ticker = yf.Ticker(symbol)
            
            # ==========================================
            # STAGE 1: FAST LIQUIDITY SCREEN (Stock Level)
            # ==========================================
            hist = ticker.history(period="3mo")
            if len(hist) < 20: continue
            
            avg_volume = hist['Volume'].mean()
            current_price = hist['Close'].iloc[-1]
            
            # AUTOMATIC LIQUIDITY GATEKEEPER 1: Stock Vol Filter
            # Instantly drops low-volume small/mid caps before fetching heavy option chains
            if avg_volume < 2000000:
                continue
            
            # Calculate Daily 20 EMA
            hist['20_EMA'] = hist['Close'].ewm(span=20, adjust=False).mean()
            current_ema = hist['20_EMA'].iloc[-1]
            is_bullish = current_price > current_ema
            trend_pct = ((current_price - current_ema) / current_ema) * 100
            
            # ==========================================
            # STAGE 2: SLOW LIQUIDITY SCREEN (Options Level)
            # ==========================================
            expirations = ticker.options
            if not expirations: continue
            
            # Target near-term monthly contracts (30-45 days out)
            target_expiry = expirations[min(2, len(expirations)-1)]
            opt_chain = ticker.option_chain(target_expiry)
            
            # Find the At-The-Money (ATM) option contract
            calls = opt_chain.calls
            if calls.empty: continue
            calls['strike_diff'] = (calls['strike'] - current_price).abs()
            atm_call = calls.sort_values(by='strike_diff').iloc[0]
            
            iv = atm_call['impliedVolatility'] * 100
            open_interest = atm_call['openInterest']
            
            # Calculate option chain spread leakage
            bid, ask = atm_call['bid'], atm_call['ask']
            spread_pct = ((ask - bid) / ((bid + ask) / 2)) * 100 if (bid + ask) > 0 else 99
            
            # AUTOMATIC LIQUIDITY GATEKEEPER 2 & 3: Options Depth Check
            if open_interest < 800 or spread_pct > 2.0:
                continue
                
            # ==========================================
            # STAGE 3: STRATEGY RULES MATRIX ROUTER
            # ==========================================
            if is_bullish and iv < 35:
                strategy = "🟢 BUY CALLS"
                reason = f"Breakout above 20 EMA. Option IV ({iv:.1f}%) is cheap for premium buying."
            elif not is_bullish and iv < 50:
                strategy = "🔴 BUY PUTS"
                reason = f"Breakdown below 20 EMA. IV ({iv:.1f}%) has not experienced an explosive spike yet."
            elif is_bullish and iv >= 55:
                strategy = "🔵 SELL CASH-SECURED PUTS"
                reason = f"Bullish trend framework holding, but elevated IV ({iv:.1f}%) provides rich CSP premium collection."
            else:
                strategy = "🟡 STAY IN CASH"
                reason = f"Asset sitting inside volatility chop zone ({iv:.1f}% IV). No clear edge."
                
            print(f"🎯 MATCH FOUND: {symbol} Passed All Filters -> {strategy}")
            
            results.append({
                "Ticker": symbol,
                "Price": round(current_price, 2),
                "vs 20-EMA": f"{trend_pct:+.1f}%",
                "Implied Vol (IV)": f"{iv:.1f}%",
                "ATM Bid-Ask Spread": f"{spread_pct:.1f}%",
                "Open Interest": int(open_interest),
                "RECOMMENDED ACTION": strategy,
                "Reasoning Breakdown": reason
            })
            
        except Exception as e:
            continue # Silently pass temporary data lookup gaps
            
    # Export clean filtered results to static spreadsheet
    df = pd.DataFrame(results)
    if not df.empty:
        df.to_csv("options_candidates.csv", index=False)
        print(f"✅ Auto-Scan Complete. Saved {len(df)} highly liquid trade configurations.")
    else:
        print("⚠️ Scan ended. Zero market assets crossed the strict liquidity thresholds today.")

if __name__ == "__main__":
    scan_market()