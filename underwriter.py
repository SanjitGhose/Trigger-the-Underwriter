import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pdfplumber
import re
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Trigger the Underwriter", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h1, h2, h3 { color: #00FFC2 !important; }
    div[data-testid="stMetric"] { background-color: #0A0A0A; border: 1px solid #1A1A1A; border-left: 5px solid #00FFC2; padding: 20px; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- ROBUST PDF PARSER ---
def parse_financials_from_pdf(file):
    # CRITICAL: Reset file pointer for every read attempt
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
                'Sundry Debtors (Receivables)': [r'Debtors', r'Receivables', r'Trade Receivables'],
                'Inventory (Stock)': [r'Inventory', r'Stock'],
                'Sundry Creditors (Trade)': [r'Creditors', r'Payables'],
                'Other Current Liabilities': [r'Other Current Liab'],
                'Short Term Bank Borrowings': [r'Short Term Borrowing', r'Working Capital Loan', r'CC Limit'],
                'Long Term Loans': [r'Long Term', r'Secured Loan'],
                'Tangible Net Worth': [r'Net Worth', r'Equity'],
                'EBITDA': [r'EBITDA', r'Operating Profit'],
                'Annual Turnover (Revenue)': [r'Turnover', r'Revenue', r'Sales'],
                'Total Raw Material Purchases': [r'Purchases', r'Cost of Materials'],
                'Interest & Finance Charges': [r'Interest', r'Finance Cost'],
                'Import Content (%)': [r'Import']
            }

            for key, patterns in mapping.items():
                for pattern in patterns:
                    match = re.search(fr"{pattern}.*?([\d,]+\.?\d*)", text, re.IGNORECASE)
                    if match:
                        val = match.group(1).replace(',', '')
                        extracted_data[key] = float(val)
                        break
    except Exception as e:
        st.error(f"PDF Analysis Error: {e}")

    # Ensure we return a dataframe with the EXACT expected column names
    final_list = []
    for key in mapping.keys():
        final_list.append({'Financial_Item': key, 'Amount_INR': extracted_data.get(key, 0.0)})
    
    return pd.DataFrame(final_list)

# --- UNDERWRITING LOGIC ---
def calculate_limits(df):
    def fetch(item):
        try: return float(df.loc[df['Financial_Item'] == item, 'Amount_INR'].values[0])
        except: return 0.0

    ca = fetch('Cash & Bank Balances') + fetch('Sundry Debtors (Receivables)') + fetch('Inventory (Stock)')
    ocl = fetch('Sundry Creditors (Trade)') + fetch('Other Current Liabilities')
    ebitda = fetch('EBITDA')
    total_debt = fetch('Short Term Bank Borrowings') + fetch('Long Term Loans')
    revenue = fetch('Annual Turnover (Revenue)')
    
    wc_limit = max(0, (ca * 0.75) - ocl)
    tl_headroom = max(0, (ebitda * 3.5) - total_debt)
    
    return {
        "WC": wc_limit, "TL": tl_headroom, "CA": ca, "OCL": ocl, "EB": ebitda, "TD": total_debt, "REV": revenue
    }

# --- MAIN APP ---
def main():
    st.title("🎯 Trigger the Underwriter")
    
    with st.sidebar:
        st.header("Upload Center")
        mode = st.radio("Source", ["Demo", "CSV", "PDF"])
        file = st.file_uploader("Upload File", type=["csv", "pdf"]) if mode != "Demo" else None

    if mode == "Demo":
        df = pd.DataFrame({
            'Financial_Item': ['Cash & Bank Balances', 'Sundry Debtors (Receivables)', 'Inventory (Stock)', 'Sundry Creditors (Trade)', 'Other Current Liabilities', 'Short Term Bank Borrowings', 'Long Term Loans', 'EBITDA', 'Annual Turnover (Revenue)'],
            'Amount_INR': [1200000, 2400000, 14000000, 6300000, 400000, 8500000, 1100000, 4900000, 78000000]
        })
    elif file:
        if mode == "CSV":
            df = pd.read_csv(file)
            # Standardize columns to avoid KeyError
            df.columns = ['Financial_Item', 'Amount_INR']
        else:
            df = parse_financials_from_pdf(file)
    else:
        st.info("Awaiting Input...")
        return

    res = calculate_limits(df)

    # UI Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("WC Limit", f"₹{res['WC']:,.0f}")
    m2.metric("Term Loan Capacity", f"₹{res['TL']:,.0f}")
    m3.metric("Total Exposure", f"₹{res['WC'] + res['TL']:,.0f}")

    # Audit Trail (The source of your KeyError)
    st.subheader("Audit Trail")
    if 'Amount_INR' in df.columns:
        # Create a copy for display to avoid modifying original data
        display_df = df.copy()
        display_df['Amount_INR'] = display_df['Amount_INR'].map('₹{:,.2f}'.format)
        st.table(display_df)
    else:
        st.error("Data structure mismatch. Please ensure CSV has 'Financial_Item' and 'Amount_INR' columns.")

if __name__ == "__main__":
    main()
