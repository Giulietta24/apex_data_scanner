# signals.py
import pandas as pd

def evaluate_signal(is_bullish_trend, iv, volume_confirmed, rsi_value, rsp_confirmed_bullish):
    """
    Unified institutional-grade options signal logic tree.
    Shared identically between the background scanner and front-end UI.
    """
    rsi_safe_long = rsi_value < 75 if not pd.isna(rsi_value) else True
    rsi_safe_short = rsi_value > 30 if not pd.isna(rsi_value) else True

    if iv > 100:
        return "⚠️ STAY IN CASH", "Asset implied volatility is abnormally high, representing excessive binary crash risk."
        
    elif is_bullish_trend and iv < 35 and volume_confirmed and rsi_safe_long:
        if rsp_confirmed_bullish:
            return "🟢 BUY CALLS", "Confirmed technical breakout above the 20-EMA. Broad market participation (RSP) is healthy."
        else:
            return "⚠️ STAY IN CASH (MARKET TRAP)", "Individual breakout detected, but Equal-Weighted S&P (RSP) is divergent. Entry blocked."
            
    elif not is_bullish_trend and iv < 50 and volume_confirmed and rsi_safe_short:
        return "🔴 BUY PUTS", "Bearish trajectory breakdown below the 20-EMA line. High distribution volume confirms institutional pressure."
        
    elif is_bullish_trend and iv >= 55:
        if rsp_confirmed_bullish:
            return "🔵 SELL CASH-SECURED PUTS", "Bullish trend structure paired with highly inflated options premiums. RSP confirms underlying index support."
        else:
            return "⚠️ STAY IN CASH (PREMIUM RISK)", "High IV premium is attractive, but broad market participation is weak. Risk of assignment is high."
            
    else:
        vol_status = "Pass" if volume_confirmed else "Fail"
        rsi_status = f"{rsi_value:.1f}" if not pd.isna(rsi_value) else "N/A"
        return "🟡 STAY IN CASH", f"Setup rejected due to internal component variance. Vol Check: {vol_status} | RSI: {rsi_status}."
