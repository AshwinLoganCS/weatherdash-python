import requests
import datetime as dt
from dateutil import parser, tz
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="WeatherDash (Python)", page_icon="🌤️", layout="wide")

# ---------- Styles: centered layout + clean cards ----------
st.markdown("""
<style>
/* Center whole app content */
.block-container {max-width: 980px; padding-top: 2rem;}

/* Card look */
.card {background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08);
       border-radius: 14px; padding: 16px 18px;}

/* Headings */
h1 {font-size: 46px; margin-bottom: 8px}
h2 {margin: 0 0 8px 0;}
.bigtemp {font-size: 56px; font-weight: 700; margin: 4px 0 8px}
.meta {opacity: .8; font-size: 14px}

/* Pill buttons */
.pill {border: 1px solid #4b5563; padding: 6px 14px; border-radius: 999px; font-weight: 600}
.pill.active {background: rgba(59,130,246,.15); border-color: #3b82f6}
.sublabel {opacity:.8; font-size: 12px}
</style>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
@st.cache_data(show_spinner=False, ttl=1800)
def geocode_suggestions(query: str, count: int = 8):
    """Return up to `count` geocoding candidates for autosuggest."""
    if not query or len(query.strip()) < 2:
        return []
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": query.strip(), "count": count, "language": "en"}, timeout=10)
    r.raise_for_status()
    return r.json().get("results", []) or []

@st.cache_data(show_spinner=False, ttl=600)
def fetch_weather(lat: float, lon: float, tz_name: str, unit: str):
    """Pull current + daily + hourly for next 48h (we’ll show 24)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "current_weather": "true",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "hourly": "temperature_2m,precipitation_probability,weathercode",
        "timezone": tz_name or "auto",
        "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
        "windspeed_unit": "mph" if unit == "F" else "kmh",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def deg_to_compass(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg/22.5) % 16]

WEATHER_MAP = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
    61: ("Light rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "⛈️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"),
    80: ("Rain showers", "🌦️"), 81: ("Rain showers", "🌧️"), 82: ("Violent rain", "⛈️"),
    85: ("Snow showers", "🌨️"), 86: ("Heavy snow", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunder w/ hail", "⛈️"), 99: ("Thunder w/ hail", "⛈️"),
}

def smart_summary(daily: dict) -> str:
    """A short readable forecast sentence: today + trend."""
    if not daily or "time" not in daily: return "Forecast unavailable."
    # Today (index 0)
    code = int(daily["weathercode"][0])
    hi = round(daily["temperature_2m_max"][0])
    lo = round(daily["temperature_2m_min"][0])
    desc = WEATHER_MAP.get(code, ("", ""))[0] or "Variable conditions"
    # Compare average next 3 days to previous 3 (if present)
    temps = daily["temperature_2m_max"][:5]
    trend = ""
    if len(temps) >= 5:
        first = sum(temps[:2]) / 2
        next3 = sum(temps[2:5]) / 3
        delta = round(next3 - first)
        if abs(delta) >= 3:
            trend = " Warming later in the week." if delta > 0 else " Cooling trend later in the week."
    return f"{desc} today — high {hi}°, low {lo}°. {trend}".strip()

def city_label(c):
    return f"{c.get('name')}, {c.get('admin1','') or ''} {c.get('country_code','') or ''}".strip()

def locate_by_ip():
    """Best-effort IP geolocation (no key)."""
    try:
        r = requests.get("https://ipapi.co/json", timeout=10)
        r.raise_for_status()
        j = r.json()
        q = f"{j.get('city','')}, {j.get('region_code','')}, {j.get('country_code','')}"
        return q.strip(", ")
    except Exception:
        return ""

# ---------- Sidebar: query + unit toggle + autosuggest + geolocate ----------
with st.sidebar:
    st.write("City (you can add state/country, e.g. 'Concord, NC, US')")
    q = st.text_input("", value="Berkeley, CA", placeholder="City, State, Country")

    cols = st.columns(2)
    unit = st.session_state.get("unit", "C")
    if cols[0].button("°C", use_container_width=True):
        unit = "C"
    if cols[1].button("°F", use_container_width=True):
        unit = "F"
    st.session_state["unit"] = unit

    # Autosuggestions
    suggestions = geocode_suggestions(q) if len(q.strip()) >= 2 else []
    chosen = None
    if suggestions:
        labels = [city_label(c) for c in suggestions]
        idx = st.selectbox("Matches", list(range(len(labels))), format_func=lambda i: labels[i])
        chosen = suggestions[idx]

    # Geolocate
    if st.button("📍 Use my location", help="IP-based location (no GPS)"):
        ip_guess = locate_by_ip()
        if ip_guess:
            q = ip_guess
            st.experimental_rerun()
        else:
            st.info("Could not determine location.")

# ---------- Resolve place ----------
place = None
if chosen:
    place = {
        "name": chosen["name"],
        "admin1": chosen.get("admin1",""),
        "country_code": chosen.get("country_code",""),
        "latitude": chosen["latitude"],
        "longitude": chosen["longitude"],
        "timezone": chosen.get("timezone","auto")
    }
else:
    # Fallback: try geocoding the raw query
    cands = geocode_suggestions(q)
    if cands:
        c0 = cands[0]
        place = {
            "name": c0["name"], "admin1": c0.get("admin1",""), "country_code": c0.get("country_code",""),
            "latitude": c0["latitude"], "longitude": c0["longitude"], "timezone": c0.get("timezone","auto")
        }

# ---------- UI: title ----------
st.markdown(f"<h1>🌤️ WeatherDash (Python)</h1>", unsafe_allow_html=True)

if not place:
    st.warning("Type at least two letters, pick a city from **Matches**, or click **Use my location**.")
    st.stop()

# ---------- Fetch data ----------
wx = fetch_weather(place["latitude"], place["longitude"], place["timezone"], unit)

# ---------- Top “hero” area ----------
city_line = f"**{place['name']}**, {place.get('admin1','')} {place.get('country_code','')}".strip()
meta = f"({place['latitude']:.2f}, {place['longitude']:.2f}) • timezone: {place['timezone']}"

cw = wx["current_weather"]
code = int(cw.get("weathercode", 0))
desc, emoji = WEATHER_MAP.get(code, ("—", "❔"))
temp_unit = "°F" if unit == "F" else "°C"
wind_unit = "mph" if unit == "F" else "km/h"
when = parser.isoparse(cw["time"]).astimezone(tz.gettz(place["timezone"])).strftime("%I:%M %p").lstrip("0")

colA, colB = st.columns([1,1])
with colA:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Current conditions")
    st.write(city_line)
    st.markdown(f'<div class="meta">{meta}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bigtemp">{round(cw["temperature"])}{temp_unit}</div>', unsafe_allow_html=True)
    st.write(f"{emoji} {desc}")
    st.write(f"💨 {round(cw['windspeed'])} {wind_unit} • 🧭 {deg_to_compass(cw['winddirection'])} • ⏱️ Updated {when}")
    st.markdown("</div>", unsafe_allow_html=True)

with colB:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 5-Day Forecast")
    d = wx["daily"]
    rows = []
    for i, day in enumerate(d["time"][:5]):
        weekday = parser.isoparse(day).strftime("%a")
        code = int(d["weathercode"][i])
        hi = round(d["temperature_2m_max"][i]); lo = round(d["temperature_2m_min"][i])
        p = d["precipitation_probability_max"][i]
        dd, ee = WEATHER_MAP.get(code, ("—", "❔"))
        rows.append(f"**{weekday}**  \n{ee} {dd}  \n**{hi} / {lo}{temp_unit}**  \n💧 {p if p is not None else '—'}%")
    st.write("\n\n".join(rows))
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Hourly chart (next 24 hours) ----------
st.markdown('<div class="card" style="margin-top:16px">', unsafe_allow_html=True)
st.subheader("Next 24 hours")

h = wx["hourly"]
df = pd.DataFrame({
    "time": pd.to_datetime(h["time"]),
    "temp": h["temperature_2m"],
    "pop": h["precipitation_probability"],
    "code": h["weathercode"],
})
# find the next 24 points from 'now' in the given timezone
now_local = dt.datetime.now(tz=tz.gettz(place["timezone"]))
df = df[df["time"] >= now_local].head(24)

# altair chart (two layered axes: temp + precip prob)
temp_chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("time:T", title="Time"),
    y=alt.Y("temp:Q", title=f"Temperature ({temp_unit})")
)
pop_chart = alt.Chart(df).mark_bar(opacity=0.25).encode(
    x="time:T",
    y=alt.Y("pop:Q", title="Precip %"),
)
st.altair_chart(alt.layer(pop_chart, temp_chart).resolve_scale(y='independent').properties(height=260, width="container"))
st.markdown("</div>", unsafe_allow_html=True)

# ---------- Smart daily summary ----------
st.markdown('<div class="card" style="margin-top:16px">', unsafe_allow_html=True)
st.subheader("Summary")
st.write(smart_summary(wx["daily"]))
st.markdown("</div>", unsafe_allow_html=True)

# footer
st.caption("Data from Open-Meteo. Built by you ✨")
