
import requests
import streamlit as st
from dateutil import parser

st.set_page_config(page_title="WeatherDash (Python)", page_icon="🌤️", layout="centered")

# -------------------- Styles (Pill Toggle) --------------------
PILL_CSS = """
<style>
.pill-wrap {display:flex; gap:8px; align-items:center;}
.pill {
  border: 1px solid #4b5563;
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
  background: transparent;
  color: inherit;
}
.pill.is-active {
  background: rgba(59,130,246,.15);
  border-color: #3b82f6;
}
.pill-label { font-weight: 600; margin-right:8px; opacity: .8; }
</style>
"""
st.markdown(PILL_CSS, unsafe_allow_html=True)

# -------------------- Helpers --------------------
@st.cache_data(show_spinner=False, ttl=1800)
def geocode_city(name: str, count: int = 10):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": name, "count": count, "language": "en"})
    r.raise_for_status()
    data = r.json()
    return data.get("results", []) or []

@st.cache_data(show_spinner=False, ttl=600)
def fetch_weather(lat: float, lon: float, tz: str, unit: str):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": tz or "auto",
        "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
        "windspeed_unit": "mph" if unit == "F" else "kmh",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

WEATHER_MAP = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
    61: ("Light rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "⛈️"),
    66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "❄️"),
    80: ("Rain showers", "🌦️"), 81: ("Rain showers", "🌧️"), 82: ("Violent rain", "⛈️"),
    85: ("Snow showers", "🌨️"), 86: ("Heavy snow", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunder w/ hail", "⛈️"), 99: ("Thunder w/ hail", "⛈️"),
}

def deg_to_compass(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg/22.5) % 16]

def pill_toggle(key: str, labels=("°C", "°F")) -> str:
    # Initialize
    if key not in st.session_state:
        st.session_state[key] = labels[0]  # default °C
    current = st.session_state[key]

    col = st.container()
    with col:
        st.markdown('<div class="pill-wrap"><span class="pill-label">Units</span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button(labels[0], key=f"{key}_a", help="Use Celsius", use_container_width=True):
                st.session_state[key] = labels[0]
        with c2:
            if st.button(labels[1], key=f"{key}_b", help="Use Fahrenheit", use_container_width=True):
                st.session_state[key] = labels[1]

        # Attempt to apply pill class to secondary buttons (best-effort; harmless if it fails)
        st.markdown(
            '<script>Array.from(window.parent.document.querySelectorAll("button[kind=\"secondary\"]")).forEach(b=>b.classList.add("pill"));</script>',
            unsafe_allow_html=True
        )

    return "F" if st.session_state[key] == labels[1] else "C"

# -------------------- UI --------------------
st.title("🌤️ WeatherDash (Python)")

with st.sidebar:
    city_query = st.text_input("City (you can add state/country, e.g. 'Concord, NC, US')", "Berkeley, US")
    unit = pill_toggle("unit_pill")  # returns "C" or "F"
    st.caption("Data from Open-Meteo (no API key).")


if not city_query.strip():
    st.stop()

# Geocode with optional hints
candidates = geocode_city(city_query)
if not candidates:
    st.error("No matches found. Try adding state/country (e.g., 'Concord, NC').")
    st.stop()

# Disambiguate if multiple results
labels = [
    f"{c.get('name')}, {c.get('admin1', '')} {c.get('country_code','')} ({{c.get('latitude'):.2f}}, {{c.get('longitude'):.2f}})"
    for c in candidates
]

choice = 0 if len(candidates) == 1 else st.selectbox("Possible matches", list(range(len(labels))), format_func=lambda i: labels[i])
place = candidates[choice]

lat, lon = place["latitude"], place["longitude"]
tz = place.get("timezone", "auto")
wx = fetch_weather(lat, lon, tz, unit)

# Layout
colL, colR = st.columns([1.2, 1])
with colL:
    st.subheader("Current conditions")
    city_line = f"**{place['name']}**, {place.get('admin1','')} {place.get('country_code','')}".strip()
    st.write(city_line)
    st.caption(f"({lat:.2f}, {lon:.2f})  •  timezone: {tz}")

    cw = wx["current_weather"]
    code = cw.get("weathercode", 0)
    desc, emoji = WEATHER_MAP.get(code, ("—", "❔"))
    temp = round(cw["temperature"])
    wind = round(cw["windspeed"])
    unit_temp = "°F" if unit == "F" else "°C"
    unit_wind = "mph" if unit == "F" else "km/h"
    when = parser.isoparse(cw["time"]).strftime("%I:%M %p").lstrip("0")

    st.markdown(f"## {temp}{unit_temp}")
    st.write(f"{emoji} {desc}")
    st.write(f"💨 {wind} {unit_wind}  •  🧭 {deg_to_compass(cw['winddirection'])}  •  ⏱️ Updated {when}")

with colR:
    st.subheader("5-Day Forecast")
    d = wx["daily"]
    for i, day in enumerate(d["time"][:5]):
        code = d["weathercode"][i]
        hi = round(d["temperature_2m_max"][i])
        lo = round(d["temperature_2m_min"][i])
        p = d["precipitation_probability_max"][i]
        desc, emoji = WEATHER_MAP.get(code, ("—", "❔"))
        weekday = parser.isoparse(day).strftime("%a")
        st.markdown(
            f"**{weekday}**  \n{emoji} {desc}  \n**{hi} / {lo}{unit_temp}**  \n💧 {p if p is not None else '—'}%"
        )
