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
        # Avoid noisy stack traces for expected API failures (e.g., 403/invalid key)
        logging.warning("Failed to fetch silver price (%s); using fallback price", e)
        return FALLBACK_SPOT


def _normalize_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns have compatible dtypes for Streamlit's data_editor.

    - Convert `Date Acquired` to `datetime.date` objects where possible.
    - Coerce numeric columns to numeric dtypes (or NaN).
    """
    df = df.copy()
    if df is None:
        return pd.DataFrame()

    if "Date Acquired" in df.columns:
        try:
            df["Date Acquired"] = pd.to_datetime(df["Date Acquired"], errors="coerce").dt.date
        except Exception:
            # leave as-is if conversion unexpectedly fails
            pass

    numeric_cols = ["Weight (troy oz)", "Weight (ozt)", "Price Paid ($)", "Modifier ($)"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

# Fetch the global spot price (cached)
with st.spinner("Fetching spot price..."):
    spot_price = get_silver_price()

# --- 3. UI HEADER & FILE UPLOADER ---
st.title("🪙 Privately track your stack")

st.caption("Track your silver inventory, calculate melt value, and see fun stats about your stack. Your data is stored locally in your browser for privacy.")

# Quick guidance about saving/loading: CSV is the canonical saved file
with st.expander("💾 How saving & loading works", expanded=False):
    st.write(
        "- Your stack is stored locally in the browser session while you work. To persist data across machines or sessions, export the CSV using the 'Download/Save Stack' button.\n"
        "- To re-load, use the CSV uploader below. The CSV should include these columns: `Description`, `Weight (troy oz)`, `Date Acquired`, `Price Paid ($)`, `Modifier ($)`.\n"
        "- `Date Acquired` should be an ISO-style date (YYYY-MM-DD) or blank. Numeric columns should contain numbers."
    )

    sample_df = pd.DataFrame([
        {
            "Description": "Example Round 1oz",
            "Weight (troy oz)": 1.0,
            "Date Acquired": date.today().isoformat(),
            "Price Paid ($)": 25.00,
            "Modifier ($)": 0.00,
        }
    ])
    sample_csv = sample_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download sample CSV", data=sample_csv, file_name="silver_stack_sample.csv", help="Download a sample CSV with the correct columns.")

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
    # Warn users if they uploaded a CSV that lacks expected columns
    expected_cols = [
        "Description",
        "Weight (troy oz)",
        "Date Acquired",
        "Price Paid ($)",
        "Modifier ($)",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        st.warning(
            f"Uploaded CSV is missing expected columns: {', '.join(missing)}. "
            "You can download the sample CSV in 'How saving & loading works' to get the correct format."
        )

    st.session_state.inventory = _normalize_inventory(df)
else:
    if "inventory" not in st.session_state:
        st.session_state.inventory = pd.DataFrame(columns=[
            "Description", "Weight (troy oz)", "Date Acquired", "Price Paid ($)", "Modifier ($)"
        ])

# Ensure any existing session inventory has compatible dtypes for the data_editor
st.session_state.inventory = _normalize_inventory(st.session_state.inventory)

# --- Add single-item entry form (privacy-preserving: stores only in browser session_state)
with st.expander("➕ Add one item"):
    with st.form("add_item_form", clear_on_submit=True):
        desc = st.text_input("Description", placeholder="e.g., Generic Round 1oz")
        weight = st.number_input("Weight (troy oz)", min_value=0.0, format="%.4f", help="Enter weight in troy ounces (e.g., 1.0000)")
        date_acq = st.date_input("Date Acquired", help="Optional: date item was acquired. Leave blank if unknown.")
        price_paid = st.number_input("Price Paid ($)", min_value=0.0, format="%.2f", help="Amount you paid for this item (optional).")
        modifier = st.number_input("Modifier ($)", format="%.2f", help="Use for retailer fees or premiums applied to melt value.")
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
st.info("Tip: After editing here, use the 'Download/Save Stack' button below to export your CSV — that exported CSV is your saved file.")
edited_df = st.data_editor(
    st.session_state.inventory,
    num_rows="dynamic",
    width='stretch',
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
        # Ensure downstream variables are defined so UI code can render safely
        total_melt = 0.0
        total_paid = 0.0
        pl = 0.0
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

    # Format numbers and style the TOTAL row to make it look like a proper footer
    fmt = {}
    if "Weight (troy oz)" in display_df.columns:
        fmt["Weight (troy oz)"] = "{:,.2f}"
    if "Price Paid ($)" in display_df.columns:
        fmt["Price Paid ($)"] = "${:,.2f}"
    if "Modifier ($)" in display_df.columns:
        fmt["Modifier ($)"] = "${:,.2f}"
    if "Item Melt Value ($)" in display_df.columns:
        fmt["Item Melt Value ($)"] = "${:,.2f}"

    def _highlight_totals(row):
        try:
            is_total = str(row.get("Description", "")).upper() == "TOTAL"
        except Exception:
            is_total = False
        if is_total:
            return ["font-weight: bold; background-color: #f5f7fa;" for _ in row.index]
        return ["" for _ in row.index]

    styled = display_df.style.format(fmt).apply(_highlight_totals, axis=1)
    # Use st.write for a pandas Styler to avoid type warnings and ensure proper rendering
    st.write(styled)

    # --- 8. SAVE BUTTON ---
    # Prepare CSV for download: canonicalize column name, then export
    csv_df = edited_df.copy()
    if "Weight (ozt)" in csv_df.columns and "Weight (troy oz)" not in csv_df.columns:
        csv_df = csv_df.rename(columns={"Weight (ozt)": "Weight (troy oz)"})

    csv = csv_df.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Download/Save Stack", data=csv, file_name=f"silver_stack_troy_oz_{date.today()}.csv")
else:
    st.info("Upload a file or add your first item in the table above to see your stats!")