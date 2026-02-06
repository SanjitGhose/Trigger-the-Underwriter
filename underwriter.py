import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import re
import yfinance as yf
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Trigger the Underwriter",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS for "Pristine" UI (High Contrast / Cyber-Banker Theme)
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { color: #00FFC2 !important; font-weight: 800; letter-spacing: -1px; }
    
    /* Metrics High Contrast */
    div[data-testid="stMetric"] {
        background-color: #0A0A0A;
        border: 2px solid #1A1A1A;
        border-left: 5px solid #00FFC2;
        padding: 20px;
        border-radius: 8px;
    }
    div[data-testid="stMetricValue"] { color: #00FFC2 !important; font-size: 2.2rem !important; }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] { background-color: #050505; border-right: 1px solid #1A1A1A; }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #111;
        color: #888;
        border-radius: 4px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #00FFC2 !important; color: #000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- PDF PARSING ENGINE ---

def parse_financials_from_pdf(file):
    """
    Expert-level extraction with pointer reset and column enforcement.
    """
    # FIX 1: Reset file pointer to handle Streamlit buffer issues
    file.seek(0)
    
    extracted_data = {}
    
    # Common keyword mapping for Indian Balance Sheets
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

    try:
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # Simplified Regex extraction
            for key, patterns in mapping.items():
                for pattern in patterns:
                    match = re.search(fr"{pattern}.*?([\d,]+\.?\d*)", text, re.IGNORECASE)
                    if match:
                        val = match.group(1).replace(',', '')
                        extracted_data[key] = float(val)
                        break
    except Exception as e:
        st.error(f"Critical PDF Error: {str(e)}")
    
    # FIX 2: Explicitly build DataFrame with standard columns to prevent KeyError
    final_list = []
    for key in mapping.keys():
        final_list.append({'Financial_Item': key, 'Amount_INR': extracted_data.get(key, 0.0)})
    
    return pd.DataFrame(final_list)


# --- TICKER DATA FETCHER ---

def fetch_financials_from_ticker(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        
        balance_sheet = stock.balance_sheet
        income_stmt = stock.income_stmt
        
        if balance_sheet.empty:
            return None, "No balance sheet data found for this ticker."
        
        latest_bs = balance_sheet.iloc[:, 0]
        latest_is = income_stmt.iloc[:, 0] if not income_stmt.empty else pd.Series()
        
        def safe_get(series, keys, default=0.0):
            if isinstance(keys, str): keys = [keys]
            for key in keys:
                if key in series.index:
                    val = series[key]
                    if pd.notna(val): return float(val)
            return default
        
        extracted_data = {
            'Cash & Bank Balances': safe_get(latest_bs, ['Cash And Cash Equivalents', 'Cash Financial', 'Cash']),
            'Sundry Debtors (Receivables)': safe_get(latest_bs, ['Receivables', 'Accounts Receivable', 'Net Receivables']),
            'Inventory (Stock)': safe_get(latest_bs, ['Inventory', 'Raw Materials']),
            'Sundry Creditors (Trade)': safe_get(latest_bs, ['Accounts Payable', 'Payables']),
            'Other Current Liabilities': safe_get(latest_bs, ['Other Current Liabilities']),
            'Short Term Bank Borrowings': safe_get(latest_bs, ['Current Debt', 'Short Long Term Debt']),
            'Long Term Loans': safe_get(latest_bs, ['Long Term Debt', 'Total Non Current Liabilities Net Minority Interest']),
            'Tangible Net Worth': safe_get(latest_bs, ['Stockholders Equity', 'Common Stock Equity']),
            'EBITDA': safe_get(latest_is, ['EBITDA', 'Normalized EBITDA', 'Operating Income']),
            'Annual Turnover (Revenue)': safe_get(latest_is, ['Total Revenue', 'Operating Revenue']),
            'Total Raw Material Purchases': safe_get(latest_is, ['Cost Of Revenue', 'Cost Of Goods Sold']),
            'Interest & Finance Charges': safe_get(latest_is, ['Interest Expense', 'Interest Expense Non Operating']),
            'Import Content (%)': 30.0,
            'Operating Cycle (Days)': 90.0
        }
        
        final_list = [{'Financial_Item': k, 'Amount_INR': v} for k, v in extracted_data.items()]
        
        info = stock.info
        return pd.DataFrame(final_list), {
            'name': info.get('longName', ticker_symbol),
            'currency': info.get('currency', 'USD'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'market_cap': info.get('marketCap', 0)
        }
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"


# --- UNDERWRITING LOGIC ---

def calculate_limits(df):
    def fetch(item):
        try: 
            # Force numeric conversion just in case
            return float(df.loc[df['Financial_Item'] == item, 'Amount_INR'].values[0])
        except: return 0.0

    cash, debtors, inventory = fetch('Cash & Bank Balances'), fetch('Sundry Debtors (Receivables)'), fetch('Inventory (Stock)')
    creditors, other_cl = fetch('Sundry Creditors (Trade)'), fetch('Other Current Liabilities')
    revenue, ebitda = fetch('Annual Turnover (Revenue)'), fetch('EBITDA')
    st_debt, lt_debt = fetch('Short Term Bank Borrowings'), fetch('Long Term Loans')
    purchases = fetch('Total Raw Material Purchases')
    interest = fetch('Interest & Finance Charges')

    ca = cash + debtors + inventory
    ocl = creditors + other_cl
    margin = 0.25 * ca
    wc_limit = max(0, ca - margin - ocl)

    total_debt = st_debt + lt_debt
    tl_headroom = max(0, (ebitda * 3.5) - total_debt)

    import_pct = fetch('Import Content (%)') or 30
    lc_limit = ((purchases * (import_pct/100)) / 12) * 4
    bg_limit = revenue * 0.10
    bill_limit = debtors * 0.80

    return {
        "WC": wc_limit, "WC_BRK": "(75% of CA - OCL)",
        "TL": tl_headroom, "TL_BRK": "(3.5x EBITDA - Total Debt)",
        "LC": lc_limit, "LC_BRK": "(Imports/12 x 4mo)",
        "BG": bg_limit, "BG_BRK": "(10% of Revenue)",
        "BILL": bill_limit, "BILL_BRK": "(80% of Debtors)",
        "DSCR": ebitda / (interest + (total_debt/5)) if (interest + (total_debt/5)) > 0 else 0,
        "LEVERAGE": total_debt / ebitda if ebitda > 0 else 0,
        "CA": ca, "OCL": ocl, "EB": ebitda, "TD": total_debt
    }


def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#666;'>Automated Credit Decisioning | Multi-Source Extraction</p>", unsafe_allow_html=True)
    st.markdown("---")

    company_info = None
    df = None

    with st.sidebar:
        st.header("Financial Gateway")
        input_type = st.radio(
            "Select Input Source", 
            ["Demo Mode", "Stock Ticker", "Upload CSV", "Upload PDF (Beta)"]
        )
        
        file = None
        ticker = None
        
        if input_type == "Stock Ticker":
            st.markdown("---")
            ticker = st.text_input("Enter Ticker Symbol", placeholder="e.g., NYKAA.NS, AAPL")
            st.caption("NSE: `.NS` | BSE: `.BO`")
        elif input_type in ["Upload CSV", "Upload PDF (Beta)"]:
            file = st.file_uploader(f"Upload Financials", type=["csv", "pdf"])

    # Processing Logic
    if input_type == "Demo Mode":
        df = pd.DataFrame({
            'Financial_Item': ['Cash & Bank Balances', 'Sundry Debtors (Receivables)', 'Inventory (Stock)', 'Sundry Creditors (Trade)', 'Other Current Liabilities', 'Short Term Bank Borrowings', 'Long Term Loans', 'Tangible Net Worth', 'EBITDA', 'Annual Turnover (Revenue)', 'Total Raw Material Purchases', 'Interest & Finance Charges', 'Import Content (%)'],
            'Amount_INR': [2000000, 6000000, 5000000, 3500000, 1000000, 2500000, 7000000, 12000000, 6500000, 45000000, 28000000, 900000, 45]
        })
    elif input_type == "Stock Ticker" and ticker:
        with st.spinner("Fetching Data..."):
            df, company_info = fetch_financials_from_ticker(ticker.upper())
    elif file and input_type == "Upload CSV":
        df = pd.read_csv(file)
        # Force column names for CSV to match internal model
        df.columns = ['Financial_Item', 'Amount_INR']
    elif file and input_type == "Upload PDF (Beta)":
        with st.spinner("Parsing PDF..."):
            df = parse_financials_from_pdf(file)

    if df is not None:
        if company_info:
            st.markdown(f"### {company_info['name']} ({company_info['sector']})")
        
        res = calculate_limits(df)
        currency_sym = "₹" if (not company_info or company_info['currency'] == 'INR') else "$"

        # I. Metrics
        st.subheader("I. Credit Limit Structuring")
        cols = st.columns(3)
        cols[0].metric("WC Limit", f"{currency_sym}{res['WC']:,.0f}")
        cols[1].metric("TL Headroom", f"{currency_sym}{res['TL']:,.0f}")
        cols[2].metric("Bill Disc.", f"{currency_sym}{res['BILL']:,.0f}")
        
        cols2 = st.columns(3)
        cols2[0].metric("LC Limit", f"{currency_sym}{res['LC']:,.0f}")
        cols2[1].metric("BG Limit", f"{currency_sym}{res['BG']:,.0f}")
        cols2[2].metric("Total Exposure", f"{currency_sym}{(res['WC']+res['TL']+res['LC']+res['BG']):,.0f}")

        # II. Mathematical Logic
        st.subheader("II. Mathematical Decision Trail")
        tabs = st.tabs(["Logic Proof", "Audit Data"])
        with tabs[0]:
            st.latex(r"MPBF_{II} = (CA \times 0.75) - OCL")
            st.info(f"**Approved WC:** {currency_sym}{res['WC']:,.0f}")
            st.latex(r"Debt_{Cap} = (EBITDA \times 3.5) - Total Debt")
            st.success(f"**Approved TL:** {currency_sym}{res['TL']:,.0f}")
        
        with tabs[1]:
            # FIX 3: Safe column access for display
            display_df = df.copy()
            # Ensure the column exists before formatting
            if 'Amount_INR' in display_df.columns:
                display_df['Amount_Formatted'] = display_df['Amount_INR'].apply(lambda x: f"{currency_sym}{x:,.2f}")
                st.table(display_df[['Financial_Item', 'Amount_Formatted']])
    else:
        st.info("Input required to generate analysis.")

if __name__ == "__main__":
    main()
