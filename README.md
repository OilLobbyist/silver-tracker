# Silver Tracker

Privately track your silver stack locally in your browser using Streamlit.

## Overview

Small, privacy-focused Streamlit app to track silver items, compute melt value using a live XAG/USD spot price, and show simple fun facts about your stack. Data lives in the browser session (`st.session_state`) and is not sent to external storage by the app.

## Features

- Upload / download CSV of your stack
- Edit items inline with the data editor
- Add a single item using the built-in form
- Cached spot price fetch (uses `METALS_API_KEY` secret if provided)

## Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. (Optional) If you have an API key for goldapi.io, set it in Streamlit secrets:

Create a file named `.streamlit/secrets.toml` with:

```toml
METALS_API_KEY = "your_api_key_here"
```

If no key is provided the app will use a safe numeric fallback price.

## Run

```bash
streamlit run app.py
```

## Privacy

All user data is stored in the browser session and in any CSV files you choose to download. The app makes one external call to fetch the spot price if `METALS_API_KEY` is configured; no user inventory data is sent to that service.

## Notes

- If you want automated tests or CI, I can add a small test harness that validates basic DataFrame behavior and price-fetch mocking.
- Dependencies are pinned in `requirements.txt` with conservative minimum versions.# silver-tracker
A state-less Python application for conveniently viewing the value of your silver
