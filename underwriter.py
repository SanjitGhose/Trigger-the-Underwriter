import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import re
import yfinance as yf

# --- PAGE CONFIGURATION (Kept the original high-contrast style) ---
st.set_page_config(page_title="Trigger the Underwriter", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #00FFC2 !important; font-weight: 800; }
    
    /* Metrics High Contrast */
    div[data-testid="stMetric"] {
        background-color: #0A0A0A;
        border: 2px solid #1A1A1A;
        border-left: 5px solid #00FFC2;
        padding: 20px;
        border-radius: 8px;
    }
    div[data-testid="stMetricValue"] { color: #00FFC2 !important; }
    
    section[data-testid="stSidebar"] { background-color: #050505; border-right: 1px solid #1A1A1A; }
</style>
""", unsafe_allow_html=True)

# --- PDF PARSING ENGINE (With Pointer Fix) ---
def parse_financials_from_pdf(file):
    # Fix 1: Ensure we start from the beginning of the file
    file.seek(0)
    extracted_data = {}
    
    try:
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            mapping = {
                'Cash & Bank Balances': [r'Cash', r'Bank Balance'],
                'Sundry Debtors (Receivables)': [r'Debtors', r'Receivables'],
                'Inventory (Stock)': [r'Inventory', r'Stock'],
                'Sundry Creditors (Trade)': [r'Creditors', r'Payables'],
                'Other Current Liabilities': [r'Other Current Liab'],
                'Short Term Bank Borrowings': [r'Short Term Borrowing', r'Working Capital'],
                'Long Term Loans': [r'Long Term', r'Term Loan'],
                'EBITDA': [r'EBITDA', r'Operating Profit'],
                'Annual Turnover (Revenue)': [r'Turnover', r'Revenue'],
                'Interest & Finance Charges': [r'Interest', r'Finance Cost']
            }

            for key, patterns in mapping.items():
                for pattern in patterns:
                    match = re.search(fr"{pattern}.*?([\d,]+\.?\d*)", text, re.IGNORECASE)
                    if match:
                        val = match.group(1).replace(',', '')
                        extracted_data[key] = float(val)
                        break
    except Exception as e:
        st.error(f"PDF Error: {e}")

    # Fix 2: Explicitly recreate the column 'Amount_INR' to avoid KeyError
    final_list = []
    for key in mapping.keys():
        final_list.append({'Financial_Item': key, 'Amount_INR': extracted_data.get(key, 0.0)})
    
    return pd.DataFrame(final_list)

# --- MAIN APP ---
def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    
    with st.sidebar:
        # NYKAA TICKER FEATURE
        st.header("Live Market Data")
        ticker_symbol = st.text_input("Enter NSE Ticker", value="NYKAA.NS")
        if ticker_symbol:
            try:
                tk = yf.Ticker(ticker_symbol)
                price = tk.info.get('currentPrice', 0)
                mcap = tk.info.get('marketCap', 0)
                st.metric(f"{ticker_symbol}", f"₹{price:,.2f}")
                st.write(f"**M-Cap:** ₹{mcap:,.0f}")
            except:
                st.error("Ticker not found")
        
        st.divider()
        st.header("Input Gateway")
        input_type = st.radio("Select Source", ["Demo Mode", "Upload PDF"])
        file = st.file_uploader("Upload Audit PDF", type=["pdf"]) if input_type == "Upload PDF" else None

    # DATA LOADING
    if input_type == "Demo Mode":
        df = pd.DataFrame({
            'Financial_Item': ['Cash & Bank Balances', 'Sundry Debtors (Receivables)', 'Inventory (Stock)', 'Sundry Creditors (Trade)', 'Other Current Liabilities', 'Short Term Bank Borrowings', 'Long Term Loans', 'EBITDA', 'Annual Turnover (Revenue)', 'Interest & Finance Charges'],
            'Amount_INR': [1249400000, 2466100000, 14175400000, 6348300000, 405200000, 8511500000, 1102100000, 4990000000, 78847000000, 1051500000]
        })
    elif file:
        df = parse_financials_from_pdf(file)
    else:
        st.info("Awaiting PDF upload to trigger logic...")
        return

    # LOGIC (Simplified for speed)
    def fetch(item):
        return float(df.loc[df['Financial_Item'] == item, 'Amount_INR'].values[0])

    ca = fetch('Cash & Bank Balances') + fetch('Sundry Debtors (Receivables)') + fetch('Inventory (Stock)')
    ocl = fetch('Sundry Creditors (Trade)') + fetch('Other Current Liabilities')
    mpbf = (ca * 0.75) - ocl

    # DASHBOARD
    st.subheader("I. Credit Risk Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("WC Limit (MPBF II)", f"₹{mpbf:,.0f}")
    c2.metric("Total Current Assets", f"₹{ca:,.0f}")
    c3.metric("Current Ratio", f"{ca/(ocl + fetch('Short Term Bank Borrowings')):.2f}x")

    st.markdown("<br>", unsafe_allow_html=True)

    # AUDIT TRAIL (The fix for your KeyError is here)
    st.subheader("II. Mathematical Audit Trail")
    # We ensure display_df ALWAYS has Amount_INR
    display_df = df.copy()
    if 'Amount_INR' in display_df.columns:
        display_df['Amount_INR'] = display_df['Amount_INR'].map('₹{:,.0f}'.format)
        st.table(display_df)

if __name__ == "__main__":
    main()
