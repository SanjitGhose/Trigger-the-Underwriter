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
    Expert-level extraction: Searches for keywords in PDF tables 
    and maps them to our internal model.
    """
    extracted_data = {}
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
            
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

        # Simplified Regex extraction for the demo logic
        for key, patterns in mapping.items():
            for pattern in patterns:
                match = re.search(fr"{pattern}.*?([\d,]+\.?\d*)", text, re.IGNORECASE)
                if match:
                    val = match.group(1).replace(',', '')
                    extracted_data[key] = float(val)
                    break
    
    final_list = []
    for key in mapping.keys():
        final_list.append({'Financial_Item': key, 'Amount_INR': extracted_data.get(key, 0.0)})
    
    return pd.DataFrame(final_list)


# --- TICKER DATA FETCHER ---

def fetch_financials_from_ticker(ticker_symbol):
    """
    Fetches balance sheet and income statement data from Yahoo Finance
    and maps it to our internal financial model.
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        
        # Fetch balance sheet and financials
        balance_sheet = stock.balance_sheet
        income_stmt = stock.income_stmt
        cash_flow = stock.cash_flow
        
        if balance_sheet.empty:
            return None, "No balance sheet data found for this ticker."
        
        # Get the most recent year's data (first column)
        latest_bs = balance_sheet.iloc[:, 0]
        latest_is = income_stmt.iloc[:, 0] if not income_stmt.empty else pd.Series()
        latest_cf = cash_flow.iloc[:, 0] if not cash_flow.empty else pd.Series()
        
        # Helper function to safely get values
        def safe_get(series, keys, default=0.0):
            if isinstance(keys, str):
                keys = [keys]
            for key in keys:
                if key in series.index:
                    val = series[key]
                    if pd.notna(val):
                        return float(val)
            return default
        
        # Map Yahoo Finance fields to our internal model
        extracted_data = {
            'Cash & Bank Balances': safe_get(latest_bs, [
                'Cash And Cash Equivalents', 
                'Cash Cash Equivalents And Short Term Investments',
                'Cash Financial',
                'Cash'
            ]),
            'Sundry Debtors (Receivables)': safe_get(latest_bs, [
                'Receivables', 
                'Accounts Receivable',
                'Net Receivables',
                'Gross Accounts Receivable'
            ]),
            'Inventory (Stock)': safe_get(latest_bs, [
                'Inventory', 
                'Raw Materials',
                'Finished Goods'
            ]),
            'Sundry Creditors (Trade)': safe_get(latest_bs, [
                'Accounts Payable', 
                'Payables',
                'Payables And Accrued Expenses'
            ]),
            'Other Current Liabilities': safe_get(latest_bs, [
                'Other Current Liabilities',
                'Current Deferred Liabilities',
                'Current Accrued Expenses'
            ]),
            'Short Term Bank Borrowings': safe_get(latest_bs, [
                'Current Debt',
                'Current Debt And Capital Lease Obligation',
                'Short Long Term Debt'
            ]),
            'Long Term Loans': safe_get(latest_bs, [
                'Long Term Debt',
                'Long Term Debt And Capital Lease Obligation',
                'Total Non Current Liabilities Net Minority Interest'
            ]),
            'Tangible Net Worth': safe_get(latest_bs, [
                'Stockholders Equity',
                'Total Equity Gross Minority Interest',
                'Common Stock Equity'
            ]),
            'EBITDA': safe_get(latest_is, [
                'EBITDA',
                'Normalized EBITDA',
                'Operating Income'
            ]),
            'Annual Turnover (Revenue)': safe_get(latest_is, [
                'Total Revenue',
                'Operating Revenue',
                'Revenue'
            ]),
            'Total Raw Material Purchases': safe_get(latest_is, [
                'Cost Of Revenue',
                'Cost Of Goods Sold'
            ]),
            'Interest & Finance Charges': safe_get(latest_is, [
                'Interest Expense',
                'Interest Expense Non Operating',
                'Net Interest Income'
            ]),
            'Import Content (%)': 30.0,  # Default - not available from yfinance
        }
        
        # Convert to DataFrame
        final_list = [{'Financial_Item': k, 'Amount_INR': v} for k, v in extracted_data.items()]
        
        # Get company info
        info = stock.info
        company_name = info.get('longName', info.get('shortName', ticker_symbol))
        currency = info.get('currency', 'USD')
        
        return pd.DataFrame(final_list), {
            'name': company_name,
            'currency': currency,
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'market_cap': info.get('marketCap', 0)
        }
        
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"


# --- UNDERWRITING LOGIC ---

def calculate_limits(df):
    def fetch(item):
        try: return float(df.loc[df['Financial_Item'] == item, 'Amount_INR'].values[0])
        except: return 0.0

    # Core Variables
    cash, debtors, inventory = fetch('Cash & Bank Balances'), fetch('Sundry Debtors (Receivables)'), fetch('Inventory (Stock)')
    creditors, other_cl = fetch('Sundry Creditors (Trade)'), fetch('Other Current Liabilities')
    revenue, ebitda = fetch('Annual Turnover (Revenue)'), fetch('EBITDA')
    st_debt, lt_debt = fetch('Short Term Bank Borrowings'), fetch('Long Term Loans')
    purchases = fetch('Total Raw Material Purchases')
    interest = fetch('Interest & Finance Charges')

    # 1. Fund Based: Working Capital (MPBF Method II)
    ca = cash + debtors + inventory
    ocl = creditors + other_cl
    margin = 0.25 * ca
    wc_limit = max(0, ca - margin - ocl)

    # 2. Fund Based: Term Loan
    total_debt = st_debt + lt_debt
    tl_headroom = max(0, (ebitda * 3.5) - total_debt)

    # 3. NFB: Letter of Credit (LC)
    import_pct = fetch('Import Content (%)') or 30
    lc_limit = ((purchases * (import_pct/100)) / 12) * 4

    # 4. NFB: Bank Guarantee (BG)
    bg_limit = revenue * 0.10

    # 5. Bill Discounting
    bill_limit = debtors * 0.80

    return {
        "WC": wc_limit, "WC_BRK": "(75% of [Cash + Debtors + Inventory] - [Creditors + Other Current Liab])",
        "TL": tl_headroom, "TL_BRK": "(3.5x EBITDA - [ST Borrowings + LT Loans])",
        "LC": lc_limit, "LC_BRK": "(Import Purchases / 12 months x 4 months lead time)",
        "BG": bg_limit, "BG_BRK": "(10% of Total Annual Turnover)",
        "BILL": bill_limit, "BILL_BRK": "(80% of Sundry Debtors)",
        "DSCR": ebitda / (interest + (total_debt/5)) if (interest + (total_debt/5)) > 0 else 0,
        "LEVERAGE": total_debt / ebitda if ebitda > 0 else 0,
        "CA": ca, "OCL": ocl, "EB": ebitda, "TD": total_debt
    }


# --- MAIN APP ---

def main():
    st.markdown("<h1>🎯 Trigger the Underwriter</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#666;'>Automated Credit Decisioning | PDF & CSV Extraction Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")

    company_info = None

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
            st.subheader("🔍 Ticker Lookup")
            ticker = st.text_input(
                "Enter Ticker Symbol",
                placeholder="e.g., RELIANCE.NS, TCS.NS, AAPL",
                help="Use .NS suffix for NSE (India), .BO for BSE. US stocks don't need suffix."
            )
            st.caption("**Examples:**")
            st.caption("• India NSE: `RELIANCE.NS`, `TCS.NS`, `INFY.NS`")
            st.caption("• India BSE: `RELIANCE.BO`, `TCS.BO`")
            st.caption("• US: `AAPL`, `GOOGL`, `MSFT`")
            
        elif input_type not in ["Demo Mode", "Stock Ticker"]:
            file = st.file_uploader(f"Upload {input_type.split()[-1]}", type=["csv", "pdf"])
        
        st.markdown("---")
        st.write("Expert Underwriter: Active")

    # Data Processing
    df = None
    
    if input_type == "Demo Mode":
        df = pd.DataFrame({
            'Financial_Item': ['Cash & Bank Balances', 'Sundry Debtors (Receivables)', 'Inventory (Stock)', 'Sundry Creditors (Trade)', 'Other Current Liabilities', 'Short Term Bank Borrowings', 'Long Term Loans', 'Tangible Net Worth', 'EBITDA', 'Annual Turnover (Revenue)', 'Total Raw Material Purchases', 'Interest & Finance Charges', 'Import Content (%)'],
            'Amount_INR': [2000000, 6000000, 5000000, 3500000, 1000000, 2500000, 7000000, 12000000, 6500000, 45000000, 28000000, 900000, 45]
        })
        
    elif input_type == "Stock Ticker":
        if ticker:
            with st.spinner(f"Fetching financial data for {ticker.upper()}..."):
                result, info = fetch_financials_from_ticker(ticker.upper())
                if result is not None:
                    df = result
                    company_info = info
                else:
                    st.error(f"⚠️ {info}")
                    return
        else:
            st.info("👈 Enter a stock ticker symbol in the sidebar to fetch financial data.")
            return
            
    elif file and input_type == "Upload CSV":
        df = pd.read_csv(file)
        
    elif file and input_type == "Upload PDF (Beta)":
        with st.spinner("Extracting financial data from PDF..."):
            df = parse_financials_from_pdf(file)
    else:
        st.info("Please select an input source or upload a document to trigger the credit engine.")
        return

    if df is None:
        return

    # Display company info if from ticker
    if company_info:
        st.markdown(f"""
        <div style='background: linear-gradient(90deg, #0A0A0A, #111); padding: 20px; border-radius: 10px; border-left: 4px solid #00FFC2; margin-bottom: 20px;'>
            <h2 style='margin:0; color:#00FFC2;'>{company_info['name']}</h2>
            <p style='color:#888; margin:5px 0;'>
                <strong>Sector:</strong> {company_info['sector']} | 
                <strong>Industry:</strong> {company_info['industry']} | 
                <strong>Currency:</strong> {company_info['currency']}
            </p>
            <p style='color:#666; margin:0;'>
                <strong>Market Cap:</strong> {company_info['currency']} {company_info['market_cap']:,.0f}
            </p>
        </div>
        """, unsafe_allow_html=True)

    res = calculate_limits(df)
    
    # Determine currency symbol
    currency_symbol = "₹" if (company_info is None or company_info.get('currency') == 'INR') else "$"
    if company_info and company_info.get('currency') not in ['INR', 'USD']:
        currency_symbol = company_info.get('currency', '$') + " "

    # DASHBOARD
    st.subheader("I. Credit Limit Structuring")
    c1, c2, c3 = st.columns(3)
    c1.metric("WC (OD/CC) Limit", f"{currency_symbol}{res['WC']:,.0f}")
    c2.metric("Term Loan Headroom", f"{currency_symbol}{res['TL']:,.0f}")
    c3.metric("Bill Discounting", f"{currency_symbol}{res['BILL']:,.0f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Letter of Credit (LC)", f"{currency_symbol}{res['LC']:,.0f}")
    c5.metric("Bank Guarantee (BG)", f"{currency_symbol}{res['BG']:,.0f}")
    c6.metric("Total Credit Exposure", f"{currency_symbol}{(res['WC']+res['TL']+res['LC']+res['BG']):,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # MATH PROOF
    st.subheader("II. Mathematical Decision Trail")
    t1, t2, t3 = st.tabs(["Fund Based Logic", "Non-Fund Based Logic", "Audit Data"])
    
    with t1:
        st.markdown("#### Working Capital (MPBF Method II)")
        st.latex(r"Limit = (Current Assets \times 0.75) - Trade Creditors")
        st.info(f"**Approved:** {currency_symbol}{res['WC']:,.0f} | **Calculation:** {res['WC_BRK']}")
        
        st.markdown("#### Term Loan Capacity")
        st.latex(r"Capacity = (EBITDA \times 3.5) - Total Debt")
        st.success(f"**Approved:** {currency_symbol}{res['TL']:,.0f} | **Calculation:** {res['TL_BRK']}")

    with t2:
        st.markdown("#### Contingent Liabilities")
        st.write(f"**Letter of Credit:** {currency_symbol}{res['LC']:,.0f} <br> *{res['LC_BRK']}*", unsafe_allow_html=True)
        st.write(f"**Bank Guarantee:** {currency_symbol}{res['BG']:,.0f} <br> *{res['BG_BRK']}*", unsafe_allow_html=True)

    with t3:
        st.write("The following items were identified and used in this decision:")
        # Format the amounts for display
        display_df = df.copy()
        display_df['Amount_INR'] = display_df['Amount_INR'].apply(lambda x: f"{currency_symbol}{x:,.2f}")
        display_df.columns = ['Financial Item', f'Amount ({company_info["currency"] if company_info else "INR"})']
        st.table(display_df)


if __name__ == "__main__":
    main()
