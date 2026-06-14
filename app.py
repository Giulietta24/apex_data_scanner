with tab5:
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
                        # Synchronize data arrays completely
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
                                # CALLS entry verification
                                if "BUY CALLS" in bt_strategy and p_close <= p_ema and c_close > c_ema:
                                    in_pos = True
                                    ent_price = float(c_close)
                                    ent_date = c_date
                                    trade_regime = "🟢 BULLISH MACRO" if macro_bullish else "⚠️ BEAR TRAP RISK"
                                    
                                # PUTS entry verification
                                elif "BUY PUTS" in bt_strategy and p_close >= p_ema and c_close < c_ema:
                                    in_pos = True
                                    ent_price = float(c_close)
                                    ent_date = c_date
                                    trade_regime = "🔴 BEARISH MACRO" if not macro_bullish else "⚠️ BULL TRAP RISK"
                            else:
                                # FIXED: Explicit return direction mapping
                                if "BUY PUTS" in bt_strategy:
                                    return_pct = (ent_price - c_close) / ent_price
                                else:
                                    return_pct = (c_close - ent_price) / ent_price
                                    
                                trade_days = (c_date - ent_date).days
                                
                                # Process exit signals with absolute tracking resets
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
                            
                            # Categorize buckets explicitly matching the trade regime assigned at generation
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
