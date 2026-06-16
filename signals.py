# signals.py
import pandas as pd

def evaluate_signal(is_bullish_trend, iv, volume_confirmed, rsi_value, rsp_confirmed_bullish, asset_class="EQUITY"):
    """
    Refined Options Signal Engine.
    Adjusted thresholds to handle high-beta growth stocks and intra-day trading.
    """
    rsi_safe_long = rsi_value < 75 if not pd.isna(rsi_value) else True
    rsi_safe_short = rsi_value > 30 if not pd.isna(rsi_value) else True

    # Context-aware IV ceilings based on asset types
    max_iv_for_calls = 38.0 if asset_class == "ETF" else 58.0

    if iv > 100:
        return "⚠️ STAY IN CASH", "Asset implied volatility is abnormally high, representing excessive binary crash risk."
        
    # --- BULLISH DIRECTIONAL SIGNAL ---
    elif is_bullish_trend and iv <= max_iv_for_calls and volume_confirmed and rsi_safe_long:
        if rsp_confirmed_bullish:
            return "🟢 BUY CALLS", "Confirmed technical breakout above the 20-EMA. Broad market participation (RSP) is healthy."
        else:
            return "⚠️ STAY IN CASH (MARKET TRAP)", "Individual breakout detected, but Equal-Weighted S&P (RSP) is divergent. Entry blocked."
            
    # --- BEARISH DIRECTIONAL SIGNAL ---
    elif not is_bullish_trend and iv < 65 and volume_confirmed and rsi_safe_short:
        return "🔴 BUY PUTS", "Bearish trajectory breakdown below the 20-EMA line. High distribution volume confirms institutional pressure."
        
    # --- PREMIUM COLLECTION SIGNAL ---
    elif is_bullish_trend and iv > max_iv_for_calls and iv <= 85:
        if rsp_confirmed_bullish:
            return "🔵 SELL CASH-SECURED PUTS", "Bullish trend structure paired with highly inflated options premiums. RSP confirms underlying index support."
        else:
            return "⚠️ STAY IN CASH (PREMIUM RISK)", "High IV premium is attractive, but broad market participation is weak. Risk of assignment is high."
            
    else:
        vol_status = "Pass" if volume_confirmed else "Fail (Low Relative Momentum)"
        rsi_status = f"{rsi_value:.1f}" if not pd.isna(rsi_value) else "N/A"
        return "🟡 STAY IN CASH", f"Setup rejected. Vol Check: {vol_status} | IV: {iv:.1f}% | RSI: {rsi_status}."
