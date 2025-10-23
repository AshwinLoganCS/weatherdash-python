# WeatherDash (Python, Streamlit)

A minimal weather app built in **Python** with **Streamlit**, using the free **Open‑Meteo** APIs (no key required).

## Features
- City search with multi‑match disambiguation (e.g., `Concord, NC, US`)
- **Pill toggle** to switch **°C ↔ °F** (wind auto‑switches **km/h ↔ mph**)
- Current conditions with emoji + 5‑day forecast
- Caching for snappy responses

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
1. Push these files to a GitHub repo.
2. Go to https://share.streamlit.io/ → “New app” → connect your repo → pick `app.py`.
3. Deploy. Done!

## APIs used
- Geocoding: https://geocoding-api.open-meteo.com/v1/search
- Forecast: https://api.open-meteo.com/v1/forecast
