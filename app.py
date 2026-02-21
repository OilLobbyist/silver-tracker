import streamlit as st
import pandas as pd
from datetime import date
import requests

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Silver Tracker", page_icon="🪙", layout="wide")

# --- 2. THE API KEY & CACHING ---
API_KEY = 'YOUR_API_KEY' # Replace with your actual key

@st.cache_data(ttl=28800)
def get_silver_price():
    try:
        url = "https://www.goldapi.io/api/XAG/USD"
        headers = {"x-access-token": API_KEY}
        response = requests.get(url, headers=headers)
        return response.json()['price'] if response.status_code == 200 else 30.00
    except Exception:
        return 30.00

spot_price = get_silver_price()

# --- 3. UI HEADER & FILE UPLOADER ---
st.title("🛡️ Private Silver Stack Tracker")

uploaded_file = st.file_uploader("📂 Import your saved stack (CSV)", type="csv")

# --- 4. INITIALIZE DATA ---
if "inventory" not in st.session_state:
    if uploaded_file is not None:
        st.session_state.inventory = pd.read_csv(uploaded_file)
    else:
        st.session_state.inventory = pd.DataFrame(columns=[
            "Description", "Weight (oz)", "Date Acquired", "Price Paid ($)", "Modifier ($)"
        ])

# --- 5. DATA ENTRY TABLE ---
st.subheader("📝 Inventory Manager")
edited_df = st.data_editor(
    st.session_state.inventory,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Date Acquired": st.column_config.DateColumn(),
        "Weight (oz)": st.column_config.NumberColumn(format="%.2f"),
        "Price Paid ($)": st.column_config.NumberColumn(format="$%.2f"),
        "Modifier ($)": st.column_config.NumberColumn(format="$%.2f"),
    }
)

# --- 6. CALCULATION & DASHBOARD ---
if not edited_df.empty and edited_df["Weight (oz)"].sum() > 0:
    edited_df["Current Melt ($)"] = (edited_df["Weight (oz)"] * spot_price) + edited_df["Modifier ($)"].fillna(0)
    
    total_oz = edited_df["Weight (oz)"].sum()
    total_melt = edited_df["Current Melt ($)"].sum()
    total_paid = edited_df["Price Paid ($)"].sum()

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Spot Price", f"${spot_price:,.2f}")
    m2.metric("Total Weight", f"{total_oz:,.2f} oz")
    m3.metric("Total Value", f"${total_melt:,.2f}")
    m4.metric("Profit/Loss", f"${total_melt - total_paid:,.2f}", delta=f"${total_melt - total_paid:,.2f}")

    # --- 7. SAVE BUTTON ---
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Download/Save Stack", data=csv, file_name=f"silver_stack_{date.today()}.csv")
else:
    st.info("Upload a file or add your first item to begin.")