import logging
from datetime import date

import pandas as pd
import requests
import math
import streamlit as st
from requests.exceptions import RequestException

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Silver Tracker", page_icon="🪙", layout="wide")

# configure basic logging (no external telemetry)
logging.basicConfig(level=logging.INFO)

# --- 2. THE API LOGIC ---
# This looks for a secret named 'METALS_API_KEY' in your settings
# conversion constants
TROY_OZ_TO_GRAMS = 31.1034768
SILVER_DENSITY_G_CM3 = 10.49
FALLBACK_SPOT = 69.00


@st.cache_data(ttl=300)
def get_silver_price():
    """Fetch the XAG/USD spot price. Cached for short periods to avoid frequent calls.

    Returns the price as a float. Uses a safe fallback when the API key is missing
    or the request fails. Does not persist any user data externally.
    """
    url = "https://www.goldapi.io/api/XAG/USD"
    api_key = st.secrets.get("METALS_API_KEY")
    if not api_key:
        logging.info("METALS_API_KEY not found in secrets; using fallback price")
        return FALLBACK_SPOT

    headers = {"x-access-token": api_key}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get("price")
        if price is None:
            logging.warning("API response missing 'price' key; using fallback")
            return FALLBACK_SPOT
        return float(price)
    except RequestException as e:
        logging.exception("Failed to fetch silver price: %s", e)
        return FALLBACK_SPOT

# Fetch the global spot price (cached)
with st.spinner("Fetching spot price..."):
    spot_price = get_silver_price()

# --- 3. UI HEADER & FILE UPLOADER ---
st.title("🪙 Privately track your stack")

st.caption("Track your silver inventory, calculate melt value, and see fun stats about your stack. Your data is stored locally in your browser for privacy.")

uploaded_file = st.file_uploader("📂 Import your saved stack (CSV)", type="csv")

# --- 4. INITIALIZE DATA ---
# If a CSV is uploaded, always load it into session_state.inventory so the
# data_editor shows the uploaded rows. Otherwise initialize an empty frame
# on first run.
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        df = pd.DataFrame(columns=[
            "Description", "Weight (troy oz)", "Date Acquired", "Price Paid ($)", "Modifier ($)"
        ])
    st.session_state.inventory = df
else:
    if "inventory" not in st.session_state:
        st.session_state.inventory = pd.DataFrame(columns=[
            "Description", "Weight (troy oz)", "Date Acquired", "Price Paid ($)", "Modifier ($)"
        ])

# --- Add single-item entry form (privacy-preserving: stores only in browser session_state)
with st.expander("➕ Add one item"):
    with st.form("add_item_form", clear_on_submit=True):
        desc = st.text_input("Description")
        weight = st.number_input("Weight (troy oz)", min_value=0.0, format="%.4f")
        date_acq = st.date_input("Date Acquired")
        price_paid = st.number_input("Price Paid ($)", min_value=0.0, format="%.2f")
        modifier = st.number_input("Modifier ($)", format="%.2f")
        add = st.form_submit_button("Add Item")
        if add:
            new_row = {
                "Description": desc,
                "Weight (troy oz)": float(weight),
                "Date Acquired": date_acq,
                "Price Paid ($)": float(price_paid),
                "Modifier ($)": float(modifier),
            }
            df = st.session_state.inventory.copy()
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.inventory = df
            st.success("Item added to your stack (stored locally in browser session).")

# --- 5. DATA ENTRY TABLE ---
st.subheader("🗂️ Your inventory")
edited_df = st.data_editor(
    st.session_state.inventory,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Date Acquired": st.column_config.DateColumn(),
        "Weight (troy oz)": st.column_config.NumberColumn(format="%.2f"),
        "Price Paid ($)": st.column_config.NumberColumn(format="$%.2f"),
        "Modifier ($)": st.column_config.NumberColumn(format="$%.2f"),
    }
)

# Persist edits back to session state so they survive reruns in the browser
st.session_state.inventory = edited_df

# --- 6. CALCULATION & DASHBOARD ---
if not edited_df.empty:
    # Coerce numeric columns and parse dates to avoid calculation errors
    if "Weight (troy oz)" in edited_df.columns:
        edited_df["Weight (troy oz)"] = pd.to_numeric(edited_df["Weight (troy oz)"], errors="coerce").fillna(0)
    else:
        # support legacy column name
        if "Weight (ozt)" in edited_df.columns:
            edited_df = edited_df.rename(columns={"Weight (ozt)": "Weight (troy oz)"})
            edited_df["Weight (troy oz)"] = pd.to_numeric(edited_df["Weight (troy oz)"], errors="coerce").fillna(0)

    for col in ["Price Paid ($)", "Modifier ($)"]:
        if col in edited_df.columns:
            edited_df[col] = pd.to_numeric(edited_df[col], errors="coerce").fillna(0)

    if "Date Acquired" in edited_df.columns:
        edited_df["Date Acquired"] = pd.to_datetime(edited_df["Date Acquired"], errors="coerce").dt.date

    total_troy_oz = edited_df.get("Weight (troy oz)", pd.Series(dtype="float")).sum()
    if total_troy_oz <= 0:
        st.info("Add items with non-zero weight to see analytics.")
    else:
        # Calculate Melt Value for the item breakdown
        edited_df["Item Melt Value ($)"] = (edited_df["Weight (troy oz)"] * spot_price) + edited_df["Modifier ($)"].fillna(0)

        total_melt = edited_df["Item Melt Value ($)"].sum()
        total_paid = edited_df["Price Paid ($)"].sum()
        pl = total_melt - total_paid

    st.divider()
    st.header("📊 Stack Analytics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Spot Price", f"${spot_price:,.2f}")
    m2.metric("Total Weight (troy oz)", f"{total_troy_oz:,.2f} troy oz")
    m3.metric("Current Melt Value", f"${total_melt:,.2f}")
    m4.metric("Profit/Loss", f"${pl:,.2f}", delta=f"${pl:,.2f}")

    # --- 7. INTERESTING STATISTICS ---
    st.subheader("💡 Fun Facts about your Stack")
    f1, f2 = st.columns(2)
    with f1:
        # Example: if drawn into a 0.5 mm diameter wire, compute approximate length
        wire_diameter_mm = 0.5
        total_grams = total_troy_oz * TROY_OZ_TO_GRAMS
        volume_cm3 = total_grams / SILVER_DENSITY_G_CM3
        radius_cm = (wire_diameter_mm / 10.0) / 2.0
        area_cm2 = math.pi * (radius_cm ** 2)
        length_cm = volume_cm3 / area_cm2 if area_cm2 > 0 else 0
        wire_miles = length_cm / 100.0 / 1609.344
        st.write(f"🧵 **The Wire Fact:** If drawn to ~{wire_diameter_mm}mm wire, length ≈ **{wire_miles:,.1f} miles**.")
        st.write(f"🔋 **Industrial Use (approx):** Roughly **{int(total_grams / 1000)} kg** of silver (use case varies).")
        # Approximate how many 12 fl oz soda cans (by mass of liquid) equal the silver stack
        cans = total_grams / 355.0
        st.write(f"🥤 **Soda Can Equivalent:** Your stack weighs about **{cans:,.1f} standard 12oz cans**.")
    with f2:
        # Use more precise constants for density
        volume = total_troy_oz * TROY_OZ_TO_GRAMS / SILVER_DENSITY_G_CM3
        st.write(f"📦 **Volume:** Your stack occupies about **{volume:,.1f} cm³**.")
        st.write(f"🛡️ **Reflectivity:** Approximately **95%** for polished silver (typical value).")

    # Detailed Table View (append a totals/footer row for display only)
    st.write("### 🔍 Detailed Item Breakdown")
    display_df = edited_df.copy()
    totals_row = {
        "Description": "TOTAL",
            "Weight (troy oz)": total_troy_oz,
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
    # Prepare CSV for download: canonicalize column name, then export
    csv_df = edited_df.copy()
    if "Weight (ozt)" in csv_df.columns and "Weight (troy oz)" not in csv_df.columns:
        csv_df = csv_df.rename(columns={"Weight (ozt)": "Weight (troy oz)"})

    csv = csv_df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Download/Save Stack", data=csv, file_name=f"silver_stack_troy_oz_{date.today()}.csv")
else:
    st.info("Upload a file or add your first item in the table above to see your stats!")