import streamlit as st
import pandas as pd
import pdfplumber
import re
import yfinance as yf

# --- PAGE CONFIGURATION (Pristine Cyber-Banker Theme) ---
st.set_page_config(page_title="Trigger the Underwriter", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #00FFC2 !important; font-weight: 800; letter-spacing: -1px; }
    div[data-testid="stMetric"] {
        background-color: #0A0A0A;
        border: 2px solid #1A1A1A; border-left: 5px solid #00FFC2;
        padding: 20px; border-radius: 8px;
    }
    div[data-testid="stMetricValue"] { color: #00FFC2 !important; font-size: 2.2rem !important; }
    section[data-testid="stSidebar"] { background-color: #050505; border-right: 1px solid #1A1A1A; }
    .stTabs [aria-selected="true"] { background-color: #00FFC2 !important; color: #000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- ROBUST PARSING ENGINE ---
def clean_numeric(val):
    if pd.isna(val): return 0.0
    # Removes ₹, %, commas, and spaces
    clean_val = re.sub(r'[^\d.]', '', str(val))
    try: return float(clean_val)
    except: return 0.0

def parse_financials(file, is_pdf=False):
    extracted_data = {}
    mapping = {
        'Cash & Bank Balances': [r'Cash'],
        'Sundry Debtors (Receivables)': [r'Debtors', r'Receivables'],
        'Inventory (Stock)': [r'Inventory', r'Stock'],
        'Sundry Creditors (Trade)': [r'Creditors', r'Payables'],
        'Other Current Liabilities': [r'Other Current Liab'],
        'Short Term Bank Borrowings': [r'Short Term Borrowing', r'Bank Borrowings'],
        'Long Term Loans': [r'Long Term'],
        'Tangible Net Worth': [r'Net Worth'],
        'EBITDA': [r'EBITDA'],
        'Annual Turnover (Revenue)': [r'Turnover', r'Revenue'],
        'Total Raw Material Purchases': [r'Purchases'],
        'Interest & Finance Charges': [r'Interest'],
        'Import Content (%)': [r'Import']
    }

    if is_pdf:
        file.seek(0)
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            for key, patterns in mapping.items():
                for pattern in patterns:
                    match = re.search(fr"{pattern}.*?([\d,]+\.\d{{2}})", text, re.IGNORECASE)
                    if match:
                        extracted_data[key] = clean_numeric(match.group(1))
                        break
    else:
        # CSV Logic: Handles the "Length Mismatch" by not forcing column names immediately
        file.seek(0)
        raw_df = pd.read_csv(file)
        # Search every cell for our keywords
        for key, patterns in mapping.items():
            for pattern in patterns:
                mask = raw_df.apply(lambda row: row.astype(str).str.contains(pattern, case=False).any(), axis=1)
                if mask.any():
                    row_idx = raw_df[mask].index[0]
                    # The value is usually in the last column of that row
                    val = raw_df.iloc[row_idx, -1]
                    extracted_data[key] = clean_numeric(val)
                    break

    # Consolidate into standard format
    final_list = [{'Financial_Item': k, 'Amount_INR': extracted_data.get(k, 0.0)} for k in mapping.keys()]
    return pd.DataFrame(final_list)

# --- UNDERWRITING LOGIC ---
def calculate_limits(df):
    def fetch(item):
        return float(df.loc[df['Financial_Item'] == item, 'Amount_INR'].values[0])

    ca = fetch('Cash & Bank Balances') + fetch('Sundry Debtors (Receivables)') + fetch('Inventory (Stock)')
    ocl = fetch('Sundry Creditors (Trade)') + fetch('Other Current Liabilities')
    ebitda = fetch('EBITDA')
    total_debt = fetch('Short Term Bank Borrowings') + fetch('Long Term Loans')
    revenue = fetch('Annual Turnover (Revenue)')
    purchases = fetch('Total Raw Material Purchases')

    wc_limit = (ca * 0.75) - ocl
    tl_headroom = (ebitda * 3.5) - total_debt
    lc_limit = ((purchases * 0.30) / 12) * 4 # Based on 30% import content
    
    return {"WC": wc_limit, "TL": tl_headroom, "LC": lc_limit, "CA": ca, "REV": revenue}

# --- MAIN APP ---
def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("Financial Gateway")
        input_type = st.radio("Source", ["Demo Mode", "Stock Ticker", "Upload CSV", "Upload PDF"])
        
        file = None
        ticker = st.text_input("Ticker (for Stock Mode)", "NYKAA.NS") if input_type == "Stock Ticker" else None
        if input_type in ["Upload CSV", "Upload PDF"]:
            file = st.file_uploader(f"Upload {input_type.split()[-1]}", type=["csv", "pdf"])

    # Processing
    df = None
    if input_type == "Demo Mode":
        df = pd.DataFrame({'Financial_Item': ['EBITDA'], 'Amount_INR': [2412793000.0]}) # Placeholder
    elif input_type == "Upload CSV" and file:
        df = parse_financials(file, is_pdf=False)
    elif input_type == "Upload PDF" and file:
        df = parse_financials(file, is_pdf=True)
    
    if df is not None:
        res = calculate_limits(df)
        
        # Dashboard
        st.subheader("I. Credit Structure")
        c1, c2, c3 = st.columns(3)
        c1.metric("WC Limit (MPBF II)", f"₹{res['WC']:,.0f}")
        c2.metric("Term Loan Headroom", f"₹{res['TL']:,.0f}")
        c3.metric("LC Limit (NFB)", f"₹{res['LC']:,.0f}")

        st.subheader("II. Mathematical Decision Trail")
        t1, t2 = st.tabs(["Logic Proof", "Audit Data"])
        with t1:
            st.latex(r"Limit = (Current Assets \times 0.75) - Creditors")
            st.info(f"Assessed Current Assets: ₹{res['CA']:,.0f}")
        with t2:
            st.table(df)

if __name__ == "__main__":
    main()
