import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import urllib3
import certifi
import os

# Fix SSL certificate issues - disable warnings and verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Disable SSL verification for urllib3
urllib3.disable_warnings()
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# --- Configuration ---
st.set_page_config(page_title="Swing Trading Copilot", layout="wide")
st.title("🦅 Swing Trading Copilot (NSE)")

# For the MVP, we use a small basket of NSE stocks. Add more as needed.
# Note: yfinance requires '.NS' for National Stock Exchange tickers.
# Using only the most liquid and reliable tickers
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", 
    "TATAMOTORS.NS", "M&M.NS", "TITAN.NS", "HDFC.NS", "ASIANPAINT.NS"
]

# --- Helper Functions ---
@st.cache_data(ttl=3600)
def fetch_and_calculate(ticker):
    """Fetches weekly data and calculates indicators securely."""
    try:
        # Fetch 2 years of weekly data with retry
        for attempt in range(3):
            try:
                df = yf.download(ticker, period="2y", interval="1wk", progress=False)
                if not df.empty:
                    break
            except Exception:
                if attempt < 2:
                    continue
                raise
        
        if df.empty:
            return None
            
        # Fix for recent yfinance MultiIndex columns: flatten them if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Calculate Indicators using pandas-ta
        df['EMA_10'] = ta.ema(df['Close'], length=10)
        df['EMA_40'] = ta.ema(df['Close'], length=40)
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        
        # Determine Signal
        df['Signal'] = "Wait"
        if len(df) > 2:
            if (df['EMA_10'].iloc[-1] > df['EMA_40'].iloc[-1]) and \
               (df['EMA_10'].iloc[-2] <= df['EMA_40'].iloc[-2]):
                df['Signal'] = "Trend Breakout (Buy)"
            elif df['RSI_14'].iloc[-1] < 35:
                df['Signal'] = "Oversold (Watch for Bounce)"
                
        return df
    except Exception as e:
        st.error(f"Error processing {ticker}: {e}")
        return None
    
# --- App Layout (Tabs) ---
tab1, tab2, tab3 = st.tabs(["📊 1. Weekly Scanner", "📈 2. Chart Validator", "📝 3. Zerodha GTT Generator"])

# ==========================================
# TAB 1: THE SCANNER
# ==========================================
# ==========================================
# TAB 1: THE SCANNER
# ==========================================
with tab1:
    st.header("Weekly Market Scan")
    st.write("Scanning basket of NSE stocks for weekly setups based on Friday's close...")
    
    if st.button("Run Weekly Scan"):
        results = []
        progress_text = "Scanning stocks. Please wait..."
        my_bar = st.progress(0, text=progress_text)
        
        for i, ticker in enumerate(TICKERS):
            df = fetch_and_calculate(ticker)
            if df is not None:
                last_row = df.iloc[-1]
                results.append({
                    "Ticker": ticker.replace(".NS", ""),
                    "Last Price": round(float(last_row['Close']), 2),
                    "RSI (14)": round(float(last_row['RSI_14']), 2) if not pd.isna(last_row['RSI_14']) else "N/A",
                    "Signal": str(last_row['Signal'])
                })
            my_bar.progress((i + 1) / len(TICKERS), text=f"Scanned {ticker}...")
            
        my_bar.empty()
        
        # Check if we actually got any results to prevent the KeyError
        if len(results) > 0:
            results_df = pd.DataFrame(results)
            
            # Highlight actionable signals safely
            def color_signals(val):
                color = 'green' if 'Buy' in str(val) else 'orange' if 'Watch' in str(val) else 'gray'
                return f'color: {color}; font-weight: bold'
            
            # Apply styling only because we proved 'Signal' exists now
            st.dataframe(results_df.style.map(color_signals, subset=['Signal']), use_container_width=True)
        else:
            st.warning("⚠️ No data could be retrieved. Please check your internet connection or ticker symbols.")


# ==========================================
# TAB 2: CHART VALIDATOR
# ==========================================
with tab2:
    st.header("Visual Validation")
    selected_ticker = st.selectbox("Select a stock to validate:", [t.replace(".NS", "") for t in TICKERS])
    
    if selected_ticker:
        full_ticker = f"{selected_ticker}.NS"
        df = fetch_and_calculate(full_ticker)
        
        if df is not None:
            # Create Plotly Chart with Volume Subplot
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.03, subplot_titles=(f'{selected_ticker} Weekly', 'Volume'),
                                row_width=[0.2, 0.7])

            # Candlestick
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                         low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            # EMAs
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_10'], line=dict(color='blue', width=1.5), name='10 EMA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_40'], line=dict(color='orange', width=1.5), name='40 EMA'), row=1, col=1)
            
            # Volume
            colors = ['green' if row['Close'] >= row['Open'] else 'red' for index, row in df.iterrows()]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

            fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 3: GTT GENERATOR
# ==========================================
with tab3:
    st.header("Zerodha GTT Order Ticket Generator")
    st.write("Calculate your exact position size and generate the numbers for your manual GTT order.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Input Risk Parameters")
        capital = st.number_input("Total Account Capital (₹)", min_value=10000, value=100000, step=10000)
        risk_pct = st.slider("Max Risk per Trade (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.1)
        entry = st.number_input("Entry Trigger Price (₹)", min_value=1.0, value=150.0, step=1.0)
        stop = st.number_input("Hard Stop Loss (₹)", min_value=1.0, value=140.0, step=1.0)
        target = st.number_input("Profit Target (₹)", min_value=1.0, value=180.0, step=1.0)

    with col2:
        st.subheader("2. Your GTT Order Ticket")
        
        if entry <= stop:
            st.error("Stop Loss must be below Entry for a long trade.")
        else:
            # The Math
            risk_amount = capital * (risk_pct / 100)
            risk_per_share = entry - stop
            quantity = int(risk_amount // risk_per_share) # Floor division for whole shares
            capital_required = quantity * entry
            potential_profit = quantity * (target - entry)
            rr_ratio = (target - entry) / (entry - stop)
            
            # The Output UI (Styled like a ticket)
            st.info(f"**Total Capital at Risk:** ₹{risk_amount:,.2f}")
            
            st.markdown(f"""
            ### 👉 ZERODHA ENTRY GTT (SINGLE)
            * **Action:** BUY
            * **Trigger Price:** `{entry}`
            * **Limit Price:** `{entry + (entry*0.001):.2f}` *(Slightly higher to ensure fill)*
            * **Quantity:** `{quantity}` shares
            * **Margin Required:** ₹{capital_required:,.2f}
            
            ---
            ### 👉 ZERODHA EXIT GTT (OCO)
            *(Place this only AFTER the entry fills)*
            * **Stop-Loss Trigger:** `{stop}`
            * **Target Trigger:** `{target}`
            * **Quantity:** `{quantity}` shares
            """)
            
            if rr_ratio >= 2.0:
                st.success(f"✅ Risk/Reward Ratio: 1 : {rr_ratio:.2f} (Excellent)")
            else:
                st.warning(f"⚠️ Risk/Reward Ratio: 1 : {rr_ratio:.2f} (Target is less than 1:2. Consider skipping.)")
