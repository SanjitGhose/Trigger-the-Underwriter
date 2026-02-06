import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import re
import yfinance as yf

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Trigger the Underwriter",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS for "Pristine" UI
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #00FFC2 !important; font-weight: 800; letter-spacing: -1px; }
    div[data-testid="stMetric"] {
        background-color: #0A0A0A;
        border: 2px solid #1A1A1A;
        border-left: 5px solid #00FFC2;
        padding: 20px;
        border-radius: 8px;
    }
    div[data-testid="stMetricValue"] { color: #00FFC2 !important; font-size: 2.2rem !important; }
    section[data-testid="stSidebar"] { background-color: #050505; border-right: 1px solid #1A1A1A; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #111; color: #888; border-radius: 4px; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #00FFC2 !important; color: #000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- ROBUST DATA CLEANING ---
def clean_numeric_value(val):
    """Handles Indian currency formatting like ' ? 58,18,64,000.00 '"""
    if pd.isna(val): return 0.0
    # Strip everything except numbers and decimal point
    clean = re.sub(r'[^\d.]', '', str(val))
    try: return float(clean)
    except: return 0.0

# --- PDF PARSING ENGINE ---
def parse_financials_from_pdf(file):
    extracted_data = {}
    with pdfplumber.open(file) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        mapping = {
            'Cash & Bank Balances': [r'Cash', r'Bank Balance'],
            'Sundry Debtors (Receivables)': [r'Debtors', r'Receivables', r'Trade Receivables'],
            'Inventory (Stock)': [r'Inventory', r'Stock', r'Closing Stock'],
            'Sundry Creditors (Trade)': [r'Creditors', r'Payables', r'Trade Payables'],
            'Other Current Liabilities': [r'Other Current Liab'],
            'Short Term Bank Borrowings': [r'Short Term Borrowing', r'Working Capital Loan', r'CC Limit'],
            'Long Term Loans': [r'Long Term', r'Secured Loan', r'Term Loan'],
            'Tangible Net Worth': [r'Net Worth', r'Equity', r'Shareholders Funds'],
            'EBITDA': [r'EBITDA', r'Operating Profit'],
            'Annual Turnover (Revenue)': [r'Turnover', r'Revenue', r'Sales'],
            'Total Raw Material Purchases': [r'Purchases', r'Cost of Materials'],
            'Interest & Finance Charges': [r'Interest', r'Finance Cost'],
            'Import Content (%)': [r'Import'],
            'Operating Cycle (Days)': [r'Cycle', r'Days']
        }

        for key, patterns in mapping.items():
            for pattern in patterns:
                # Look for number following the pattern
                match = re.search(fr"{pattern}.*?([\d,]+\.?\d*)", text, re.IGNORECASE)
                if match:
                    extracted_data[key] = clean_numeric_value(match.group(1))
                    break
    
    final_list = [{'Financial_Item': k, 'Amount_INR': extracted_data.get(k, 0.0)} for k in mapping.keys()]
    return pd.DataFrame(final_list)

# --- TICKER DATA FETCHER ---
def fetch_financials_from_ticker(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        bs = stock.balance_sheet
        is_ = stock.income_stmt
        if bs.empty: return None, "No data found."
        
        latest_bs = bs.iloc[:, 0]
        latest_is = is_.iloc[:, 0] if not is_.empty else pd.Series()
        
        def safe_get(series, keys):
            for k in keys:
                if k in series.index and pd.notna(series[k]): return float(series[k])
            return 0.0
        
        data = {
            'Cash & Bank Balances': safe_get(latest_bs, ['Cash And Cash Equivalents', 'Cash']),
            'Sundry Debtors (Receivables)': safe_get(latest_bs, ['Receivables', 'Accounts Receivable']),
            'Inventory (Stock)': safe_get(latest_bs, ['Inventory']),
            'Sundry Creditors (Trade)': safe_get(latest_bs, ['Accounts Payable', 'Payables']),
            'Other Current Liabilities': safe_get(latest_bs, ['Other Current Liabilities']),
            'Short Term Bank Borrowings': safe_get(latest_bs, ['Current Debt']),
            'Long Term Loans': safe_get(latest_bs, ['Long Term Debt']),
            'Tangible Net Worth': safe_get(latest_bs, ['Stockholders Equity']),
            'EBITDA': safe_get(latest_is, ['EBITDA', 'Operating Income']),
            'Annual Turnover (Revenue)': safe_get(latest_is, ['Total Revenue']),
            'Total Raw Material Purchases': safe_get(latest_is, ['Cost Of Revenue']),
            'Interest & Finance Charges': safe_get(latest_is, ['Interest Expense']),
            'Import Content (%)': 30.0
        }
        
        info = stock.info
        df = pd.DataFrame([{'Financial_Item': k, 'Amount_INR': v} for k, v in data.items()])
        return df, {'name': info.get('longName', ticker_symbol), 'currency': info.get('currency', 'USD'), 
                    'sector': info.get('sector', 'N/A'), 'market_cap': info.get('marketCap', 0)}
    except Exception as e: return None, str(e)

# --- UNDERWRITING LOGIC ---
def calculate_limits(df):
    def fetch(item):
        try:
            # Flexible matching to find row containing item name
            mask = df.iloc[:, 0].astype(str).str.contains(item, case=False, na=False)
            if not mask.any(): 
                mask = df.iloc[:, 1].astype(str).str.contains(item, case=False, na=False)
            
            # Get the last numeric value in that row
            row = df[mask].iloc[0]
            for val in reversed(row):
                num = clean_numeric_value(val)
                if num != 0: return num
            return 0.0
        except: return 0.0

    # Logic Variables
    cash, debtors, inventory = fetch('Cash'), fetch('Debtors'), fetch('Inventory')
    creditors, other_cl = fetch('Creditors'), fetch('Other Current')
    revenue, ebitda = fetch('Turnover'), fetch('EBITDA')
    st_debt, lt_debt = fetch('Short Term'), fetch('Long Term')
    purchases, interest = fetch('Purchases'), fetch('Interest')

    # Calculations
    ca = cash + debtors + inventory
    ocl = creditors + other_cl
    wc_limit = max(0, (ca * 0.75) - ocl)
    total_debt = st_debt + lt_debt
    tl_headroom = max(0, (ebitda * 3.5) - total_debt)
    
    import_pct = fetch('Import') or 30
    lc_limit = ((purchases * (import_pct/100)) / 12) * 4
    bg_limit = revenue * 0.10
    bill_limit = debtors * 0.80

    return {
        "WC": wc_limit, "WC_BRK": f"(75% of {ca:,.0f} [CA] - {ocl:,.0f} [OCL])",
        "TL": tl_headroom, "TL_BRK": f"(3.5x {ebitda:,.0f} [EB] - {total_debt:,.0f} [Debt])",
        "LC": lc_limit, "LC_BRK": f"(Imports / 12 months x 4 months lead time)",
        "BG": bg_limit, "BG_BRK": "(10% of Annual Turnover)",
        "BILL": bill_limit, "BILL_BRK": "(80% of Sundry Debtors)",
        "CA": ca, "OCL": ocl, "EB": ebitda, "TD": total_debt
    }

# --- MAIN APP ---
def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#666;'>Automated Credit Decisioning | Intelligent Extraction</p>", unsafe_allow_html=True)
    st.markdown("---")

    df = None
    company_info = None

    with st.sidebar:
        st.header("Financial Gateway")
        input_type = st.radio("Source", ["Demo Mode", "Stock Ticker", "Upload CSV", "Upload PDF"])
        
        if input_type == "Stock Ticker":
            ticker = st.text_input("Ticker Symbol").upper()
            if ticker:
                df, company_info = fetch_financials_from_ticker(ticker)
        elif input_type == "Demo Mode":
            df = pd.DataFrame({'Financial_Item': ['Cash', 'Debtors', 'Inventory', 'Creditors', 'Other Current', 'Short Term', 'Long Term', 'EBITDA', 'Turnover', 'Purchases', 'Interest', 'Import'],
                               'Amount_INR': [2e6, 6e6, 5e6, 3.5e6, 1e6, 2.5e6, 7e6, 6.5e6, 45e6, 28e6, 9e5, 45]})
        else:
            file = st.file_uploader(f"Upload {input_type}", type=["csv", "pdf"])
            if file:
                if input_type == "Upload CSV":
                    # Fix for the ValueError: we read the CSV and let the fetch function find the data
                    df = pd.read_csv(file)
                else:
                    df = parse_financials_from_pdf(file)

    if df is not None:
        res = calculate_limits(df)
        sym = "₹" if (not company_info or company_info['currency'] == 'INR') else "$"

        # Dashboard
        st.subheader("I. Credit Limit Structuring")
        c1, c2, c3 = st.columns(3)
        c1.metric("WC (OD/CC) Limit", f"{sym}{res['WC']:,.0f}")
        c2.metric("Term Loan Headroom", f"{sym}{res['TL']:,.0f}")
        c3.metric("Bill Discounting", f"{sym}{res['BILL']:,.0f}")

        c4, c5, c6 = st.columns(3)
        c4.metric("Letter of Credit (LC)", f"{sym}{res['LC']:,.0f}")
        c5.metric("Bank Guarantee (BG)", f"{sym}{res['BG']:,.0f}")
        c6.metric("Total Credit Exposure", f"{sym}{(res['WC']+res['TL']+res['LC']+res['BG']):,.0f}")

        # Math Proof
        st.subheader("II. Mathematical Decision Trail")
        t1, t2, t3 = st.tabs(["Fund Based Logic", "Non-Fund Based Logic", "Audit Data"])
        
        with t1:
            st.markdown("#### Working Capital (MPBF Method II)")
            st.latex(r"Limit = (Current Assets \times 0.75) - Trade Creditors")
            st.info(f"**Approved:** {sym}{res['WC']:,.0f}  \n**Trail:** {res['WC_BRK']}")
            st.markdown("#### Term Loan Capacity")
            st.latex(r"Capacity = (EBITDA \times 3.5) - Total Debt")
            st.success(f"**Approved:** {sym}{res['TL']:,.0f}  \n**Trail:** {res['TL_BRK']}")

        with t2:
            st.markdown("#### Contingent Liabilities")
            st.write(f"**Letter of Credit:** {sym}{res['LC']:,.0f}  \n*{res['LC_BRK']}*")
            st.write(f"**Bank Guarantee:** {sym}{res['BG']:,.0f}  \n*{res['BG_BRK']}*")

        with t3:
            st.write("Identified audit trail for this decision:")
            st.table(df)

if __name__ == "__main__":
    main()
