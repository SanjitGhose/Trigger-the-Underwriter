import streamlit as st
import pandas as pd
import pdfplumber
import re
import yfinance as yf

# --- PAGE CONFIGURATION ---
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
</style>
""", unsafe_allow_html=True)

# --- ROBUST PARSING ENGINE ---
def clean_numeric(val):
    if pd.isna(val): return 0.0
    # Handles Indian format: removes currency symbols, commas, and whitespace
    clean_val = str(val).replace('?', '').replace('₹', '').replace(',', '').strip()
    # Extracts the first float-like string found
    match = re.search(r"(\d+\.?\d*)", clean_val)
    try: return float(match.group(1)) if match else 0.0
    except: return 0.0

def parse_financials(file, is_pdf=False):
    extracted_data = {}
    # Enhanced mapping to match ORIANA keys exactly 
    mapping = {
        'Cash & Bank Balances': [r'Cash & Bank Balances'],
        'Sundry Debtors (Receivables)': [r'Sundry Debtors', r'Receivables'],
        'Inventory (Stock)': [r'Inventory', r'Stock'],
        'Sundry Creditors (Trade)': [r'Sundry Creditors', r'Trade Payables'],
        'Other Current Liabilities': [r'Other Current Liabilities'],
        'Short Term Bank Borrowings': [r'Short Term Bank Borrowings'],
        'Long Term Loans': [r'Long Term Loans'],
        'EBITDA': [r'EBITDA'],
        'Annual Turnover (Revenue)': [r'Annual Turnover', r'Revenue'],
        'Total Raw Material Purchases': [r'Total Raw Material Purchases'],
        'Interest & Finance Charges': [r'Interest & Finance Charges'],
        'Import Content (%)': [r'Import Content']
    }

    if is_pdf:
        file.seek(0)
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            for key, patterns in mapping.items():
                for pattern in patterns:
                    # Specific regex for ORIANA PDF format 
                    match = re.search(fr"{pattern}.*?([\d,]+\.\d{{2}})", text, re.IGNORECASE | re.DOTALL)
                    if match:
                        extracted_data[key] = clean_numeric(match.group(1))
                        break
    else:
        file.seek(0)
        raw_df = pd.read_csv(file)
        # Search rows for mapping keywords 
        for _, row in raw_df.iterrows():
            row_str = " ".join(row.astype(str))
            for key, patterns in mapping.items():
                for pattern in patterns:
                    if re.search(pattern, row_str, re.IGNORECASE):
                        # Extract the last numeric-looking item in the row
                        nums = [clean_numeric(item) for item in row if str(item).replace('.','').replace(',','').strip().isdigit() or '?' in str(item)]
                        if nums: extracted_data[key] = nums[-1]
                        break

    final_list = [{'Financial_Item': k, 'Amount_INR': extracted_data.get(k, 0.0)} for k in mapping.keys()]
    return pd.DataFrame(final_list)

# --- UNDERWRITING LOGIC ---
def calculate_limits(df):
    def fetch(item):
        # FIX: Added try-except and empty check to prevent IndexError
        try:
            val = df.loc[df['Financial_Item'].str.contains(item, case=False, na=False), 'Amount_INR']
            return float(val.values[0]) if not val.empty else 0.0
        except Exception:
            return 0.0

    # Variable assignment using the safe fetch
    cash = fetch('Cash & Bank Balances')
    debtors = fetch('Sundry Debtors')
    inventory = fetch('Inventory')
    creditors = fetch('Sundry Creditors')
    other_cl = fetch('Other Current Liabilities')
    ebitda = fetch('EBITDA')
    st_debt = fetch('Short Term Bank Borrowings')
    lt_debt = fetch('Long Term Loans')
    revenue = fetch('Annual Turnover')
    purchases = fetch('Total Raw Material Purchases')

    # MPBF II Calculation
    ca = cash + debtors + inventory
    ocl = creditors + other_cl
    wc_limit = (ca * 0.75) - ocl
    total_debt = st_debt + lt_debt
    tl_headroom = (ebitda * 3.5) - total_debt
    
    return {"WC": wc_limit, "TL": tl_headroom, "CA": ca, "OCL": ocl, "REV": revenue, "EB": ebitda}

def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("Financial Gateway")
        input_type = st.radio("Source", ["Upload PDF", "Upload CSV", "Stock Ticker"])
        file = st.file_uploader(f"Upload File", type=["pdf", "csv"]) if "Upload" in input_type else None
        ticker = st.text_input("NSE Ticker", "NYKAA.NS") if input_type == "Stock Ticker" else None

    df = None
    if file:
        df = parse_financials(file, is_pdf=(input_type == "Upload PDF"))
    elif ticker:
        # Stock Ticker logic as previously defined
        pass

    if df is not None:
        res = calculate_limits(df)
        
        # Dashboard UI
        st.subheader("I. Credit Structure")
        c1, c2, c3 = st.columns(3)
        c1.metric("WC Limit (MPBF II)", f"₹{res['WC']:,.0f}")
        c2.metric("Term Loan Headroom", f"₹{res['TL']:,.0f}")
        c3.metric("Current Ratio", f"{(res['CA']/res['OCL']):.2f}x" if res['OCL'] > 0 else "N/A")

        st.subheader("II. Mathematical Decision Trail")
        t1, t2 = st.tabs(["Logic Proof", "Audit Data"])
        with t1:
            st.latex(r"Limit = (Current Assets \times 0.75) - OCL")
            st.info(f"Assessed EBITDA: ₹{res['EB']:,.0f}")
        with t2:
            st.table(df)

if __name__ == "__main__":
    main()
