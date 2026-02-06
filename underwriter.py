import streamlit as st
import pandas as pd
import yfinance as yf
import pdfplumber
import re
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(page_title="Trigger Underwriter + Ticker", page_icon="📈", layout="wide")

# Custom CSS for that "Banker's Terminal" look
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    [data-testid="stMetricValue"] { color: #00ffc2 !important; }
    .stTable { border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# --- 1. LIVE STOCK TICKER FEATURE ---
def render_stock_ticker(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        hist = ticker.history(period="1mo")
        
        # Display Header
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(f"📊 Market View: {info.get('longName', ticker_symbol)}")
        with col2:
            current_price = info.get('currentPrice', 0)
            prev_close = info.get('previousClose', 1)
            delta = ((current_price - prev_close) / prev_close) * 100
            st.metric("Live Price", f"₹{current_price:,.2f}", f"{delta:+.2f}%")

        # Market Stats
        m1, m2, m3 = st.columns(3)
        m1.write(f"**Market Cap:** ₹{info.get('marketCap', 0):,}")
        m2.write(f"**52W High:** ₹{info.get('fiftyTwoWeekHigh', 0)}")
        m3.write(f"**P/E Ratio:** {info.get('trailingPE', 'N/A')}")

        # Sparkline Chart
        fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], line=dict(color='#00ffc2', width=2))])
        fig.update_layout(height=150, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_view=True)
        
    except Exception as e:
        st.sidebar.error(f"Ticker Error: {e}")

# --- 2. ROBUST PDF PARSER (With Reset Logic) ---
def parse_financials(file):
    file.seek(0) # Critical: Reset pointer
    extracted_data = {}
    with pdfplumber.open(file) as pdf:
        full_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
    # Dictionary of standard credit items
    mapping = {
        'Cash & Bank Balances': r'(?:Cash|Bank Balance).*?([\d,]+\.?\d*)',
        'Sundry Debtors (Receivables)': r'(?:Debtors|Receivables).*?([\d,]+\.?\d*)',
        'Inventory (Stock)': r'(?:Inventory|Stock).*?([\d,]+\.?\d*)',
        'Sundry Creditors (Trade)': r'(?:Creditors|Payables).*?([\d,]+\.?\d*)',
        'EBITDA': r'EBITDA.*?([\d,]+\.?\d*)',
        'Annual Turnover (Revenue)': r'(?:Turnover|Revenue).*?([\d,]+\.?\d*)'
    }

    for key, pattern in mapping.items():
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            extracted_data[key] = float(match.group(1).replace(',', ''))
        else:
            extracted_data[key] = 0.0

    return pd.DataFrame(list(extracted_data.items()), columns=['Financial_Item', 'Amount_INR'])

# --- 3. MAIN APP INTERFACE ---
def main():
    st.title("🎯 Underwriter Terminal")

    # SIDEBAR
    with st.sidebar:
        st.header("1. Market Intelligence")
        ticker_input = st.text_input("Enter NSE Ticker", value="NYKAA.NS")
        render_stock_ticker(ticker_input)
        
        st.divider()
        st.header("2. Credit Analysis")
        input_type = st.radio("Data Source", ["PDF Upload", "Manual Demo"])
        uploaded_file = st.file_uploader("Upload Audit PDF", type="pdf") if input_type == "PDF Upload" else None

    # LOGIC SWITCH
    if input_type == "Manual Demo":
        df = pd.DataFrame({
            'Financial_Item': ['Cash & Bank Balances', 'Sundry Debtors (Receivables)', 'Inventory (Stock)', 'Sundry Creditors (Trade)'],
            'Amount_INR': [1249400000, 2466100000, 14175400000, 6348300000]
        })
    elif uploaded_file:
        df = parse_financials(uploaded_file)
    else:
        st.warning("Please upload a PDF or switch to Demo mode.")
        return

    # CALCULATIONS
    ca = df.loc[df['Financial_Item'].str.contains('Cash|Debtors|Inventory'), 'Amount_INR'].sum()
    ocl = df.loc[df['Financial_Item'].str.contains('Creditors'), 'Amount_INR'].sum()
    wc_gap = ca - ocl
    mpbf_ii = (ca * 0.75) - ocl

    # DASHBOARD
    st.subheader("Financial Underwriting Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Current Assets", f"₹{ca/1e7:,.2f} Cr")
    c2.metric("Working Capital Gap", f"₹{wc_gap/1e7:,.2f} Cr")
    c3.metric("Eligible Bank Limit", f"₹{mpbf_ii/1e7:,.2f} Cr")

    st.divider()
    st.write("### Data Audit Trail")
    # Using fixed names to avoid the KeyError you experienced
    display_df = df.copy()
    display_df['Amount (Formatted)'] = display_df['Amount_INR'].map(lambda x: f"₹{x:,.2f}")
    st.dataframe(display_df[['Financial_Item', 'Amount (Formatted)']], use_container_width=True)

if __name__ == "__main__":
    main()
