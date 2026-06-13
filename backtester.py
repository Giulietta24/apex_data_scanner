# backtester.py
import yfinance as yf
import pandas as pd
import numpy as np

def run_backtest(symbol, years=3, profit_target=0.05, stop_loss=0.03):
    print(f"📊 Pulling {years} years of historical data for {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=f"{years}y")
    
    if df.empty or len(df) < 50:
        print("❌ Insufficient data found for backtesting.")
        return

    # Calculate indicators
    df['20_EMA'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Track states
    in_position = False
    entry_price = 0
    entry_date = None
    trades = []
    
    print("🏃‍♂️ Running day-by-day historical simulation loop...")
    for i in range(20, len(df)):
        current_date = df.index[i]
        current_close = df['Close'].iloc[i]
        prev_close = df['Close'].iloc[i-1]
        current_ema = df['20_EMA'].iloc[i]
        prev_ema = df['20_EMA'].iloc[i-1]
        
        if not in_position:
            # ENTRY CONDITION: Price crosses ABOVE the 20-EMA
            if prev_close <= prev_ema and current_close > current_ema:
                in_position = True
                entry_price = current_close
                entry_date = current_date
        else:
            # EXIT CONDITIONS: Check profit target, stop loss, or 21-day time limit
            price_change = (current_close - entry_price) / entry_price
            days_in_trade = (current_date - entry_date).days
            
            # 1. Take Profit
            if price_change >= profit_target:
                trades.append({"entry_date": entry_date, "exit_date": current_date, "return": profit_target, "result": "WIN"})
                in_position = False
            # 2. Stop Loss
            elif price_change <= -stop_loss:
                trades.append({"entry_date": entry_date, "exit_date": current_date, "return": -stop_loss, "result": "LOSS"})
                in_position = False
            # 3. Time-based Expiration Exit (roughly 1 month)
            elif days_in_trade >= 30:
                trades.append({"entry_date": entry_date, "exit_date": current_date, "return": price_change, "result": "TIMEOUT"})
                in_position = False

    # Render Report Metrics
    if not trades:
        print("🟡 Backtest complete: Zero setups triggered your entry rules in this timeframe.")
        return
        
    trade_df = pd.DataFrame(trades)
    total_trades = len(trade_df)
    wins = len(trade_df[trade_df['result'] == 'WIN'])
    losses = len(trade_df[trade_df['result'] == 'LOSS'])
    timeouts = len(trade_df[trade_df['result'] == 'TIMEOUT'])
    
    win_rate = (wins / total_trades) * 100
    compounded_return = (np.prod(1 + trade_df['return']) - 1) * 100
    buy_and_hold = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100

    print("\n" + "="*45)
    print(f"🎯 BACKTEST PERFORMANCE REPORT: {symbol}")
    print("="*45)
    print(f"📋 Total Signals Triggered: {total_trades}")
    print(f"✅ Winning Trades:           {wins} ({win_rate:.1f}%)")
    print(f"❌ Losing Trades:            {losses}")
    print(f"⏱️ Time-expired Exits:       {timeouts}")
    print("-"*45)
    print(f"📈 Compounded Strategy Return: {compounded_return:+.1f}%")
    print(f"💰 Benchmark Buy & Hold Return: {buy_and_hold:+.1f}%")
    print("="*45)

if __name__ == "__main__":
    # Test it out on SPY across the last 3 years
    run_backtest("SPY", years=3)
