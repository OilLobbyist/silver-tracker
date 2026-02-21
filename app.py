import streamlit as st
import pandas as pd
from datetime import date
import requests

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Silver Tracker", page_icon="🪙", layout="wide")

# --- 2. THE API LOGIC ---
# This looks for a secret named 'METALS_API_KEY' in your settings
def get_silver_price():
    try:
        # Check if the secret exists, otherwise use a fallback
        api_key = st.secrets["METALS_API_KEY"]
        url = "https://www.goldapi.io/api/XAG/USD"
        headers = {"x-access-token": api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()['price']
        return 30.00
    except:
        # If the secret isn't set yet or API fails, we use this fallback
        return 30.00

# Fetch the global spot price
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
    # Calculate Melt Value for the item breakdown
    edited_df["Item Melt Value ($)"] = (edited_df["Weight (oz)"] * spot_price) + edited_df["Modifier ($)"].fillna(0)
    
    total_oz = edited_df["Weight (oz)"].sum()
    total_melt = edited_df["Item Melt Value ($)"].sum()
    total_paid = edited_df["Price Paid ($)"].sum()
    pl = total_melt - total_paid

    st.divider()
    st.header("📊 Stack Analytics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Spot Price", f"${spot_price:,.2f}")
    m2.metric("Total Weight", f"{total_oz:,.2f} oz")
    m3.metric("Current Melt Value", f"${total_melt:,.2f}")
    m4.metric("Profit/Loss", f"${pl:,.2f}", delta=f"${pl:,.2f}")

    # --- 7. INTERESTING STATISTICS ---
    st.subheader("💡 Fun Facts about your Stack")
    f1, f2 = st.columns(2)
    with f1:
        wire_miles = total_oz * 1.5
        st.write(f"🧵 **The Wire Fact:** Your silver could be drawn into a wire **{wire_miles:,.1f} miles** long!")
        st.write(f"🔋 **Industrial Use:** You have enough silver for roughly **{int(total_oz * 1.5)} solar panels**.")
        # Approximate how many 12 fl oz soda cans (by mass of liquid) equal the silver stack
        cans = (total_oz * 31.1) / 355
        st.write(f"🥤 **Soda Can Equivalent:** Your stack weighs about **{cans:,.1f} standard 12oz cans**.")
    with f2:
        # Silver density is roughly 10.5 g/cm3
        volume = (total_oz * 31.1) / 10.5
        st.write(f"📦 **Volume:** Your stack takes up about **{volume:,.1f} cubic centimeters**.")
        st.write(f"🛡️ **Reflectivity:** Your stack reflects **95%** of all light, the highest of any metal!")

    # Detailed Table View (append a totals/footer row for display only)
    st.write("### 🔍 Detailed Item Breakdown")
    display_df = edited_df.copy()
    totals_row = {
        "Description": "TOTAL",
        "Weight (oz)": total_oz,
        "Date Acquired": "",
        "Price Paid ($)": total_paid,
        "Modifier ($)": "",
        "Item Melt Value ($)": total_melt,
    }
    # Ensure we only add keys that exist in the current frame (keeps compatibility)
    totals_row = {k: v for k, v in totals_row.items() if k in display_df.columns}
    display_df = pd.concat([display_df, pd.DataFrame([totals_row])], ignore_index=True)
    st.dataframe(display_df, use_container_width=True)

    # --- 8. SAVE BUTTON ---
    csv = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Download/Save Stack", data=csv, file_name=f"silver_stack_{date.today()}.csv")
else:
    st.info("Upload a file or add your first item in the table above to see your stats!")