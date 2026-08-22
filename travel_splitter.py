import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import date
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import io

# --- 1. Page Configuration & Ultra-Modern Cyber-Glass Theme ---
st.set_page_config(
    page_title="Travel Companion OS",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

    :root {
        --bg-glass: rgba(255, 255, 255, 0.85);
        --border-glass: #e2e8f0;
        --text-primary: #0f172a;
        --text-secondary: #64748b;
        --accent-glow: #0284c7;
        --accent-gradient: linear-gradient(135deg, #0284c7 0%, #0ea5e9 50%, #38bdf8 100%);
        --card-bg: #ffffff;
        --badge-bg: #f0f9ff;
        --card-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.02);
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg-glass: rgba(15, 23, 42, 0.8);
            --border-glass: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-glow: #38bdf8;
            --accent-gradient: linear-gradient(135deg, #0369a1 0%, #0284c7 50%, #38bdf8 100%);
            --card-bg: #1e293b;
            --badge-bg: #0c4a6e;
            --card-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.3);
        }
    }

    [data-theme="dark"] {
        --bg-glass: rgba(15, 23, 42, 0.8);
        --border-glass: #334155;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --accent-glow: #38bdf8;
        --accent-gradient: linear-gradient(135deg, #0369a1 0%, #0284c7 50%, #38bdf8 100%);
        --card-bg: #1e293b;
        --badge-bg: #0c4a6e;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .font-brand {
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: -0.02em;
    }

    /* Glassmorphism Cards */
    .glass-card {
        background: var(--card-bg);
        border: 1px solid var(--border-glass);
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 16px;
        box-shadow: var(--card-shadow);
        backdrop-filter: blur(16px);
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease;
    }
    .glass-card:hover {
        transform: translateY(-3px);
    }

    /* Weather Radar Glass Widget */
    .radar-card {
        background: var(--accent-gradient);
        border-radius: 20px;
        padding: 24px;
        color: white;
        box-shadow: 0 15px 35px -5px rgba(2, 132, 199, 0.45);
        position: relative;
        overflow: hidden;
    }

    .radar-badge {
        background: rgba(255, 255, 255, 0.22);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        backdrop-filter: blur(8px);
    }

    /* Micro Badges */
    .chip-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--badge-bg);
        color: var(--accent-glow);
        font-weight: 700;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 8px;
        border: 1px solid var(--border-glass);
    }

    /* Tab Custom Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: var(--card-bg);
        padding: 6px;
        border-radius: 14px;
        border: 1px solid var(--border-glass);
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 10px;
        font-weight: 600;
        color: var(--text-secondary);
        border: none !important;
        padding: 0 18px;
    }
    .stTabs [aria-selected="true"] {
        background: var(--accent-glow) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35) !important;
    }

    /* Button Glows */
    .stButton > button {
        border-radius: 9999px;
        background-color: var(--accent-glow);
        color: white;
        font-weight: 700;
        border: none;
        padding: 0.55rem 1.6rem;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 6px 20px rgba(2, 132, 199, 0.4);
        transform: translateY(-1px);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Layer with Extended Metadata & Wishlist ---
DB_FILE = "trip_expenses.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Expenses Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            amount_foreign REAL,
            currency TEXT,
            exchange_rate REAL,
            amount_home REAL,
            paid_by TEXT,
            category TEXT,
            expense_date TEXT,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            trip_day INTEGER DEFAULT 1
        )
    """)
    # Wishlist & Bucket List Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            estimated_cost REAL,
            location_name TEXT,
            status TEXT DEFAULT 'Planning'
        )
    """)
    conn.commit()
    conn.close()

def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date, loc_name, lat, lon, trip_day):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date, location_name, latitude, longitude, trip_day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date, loc_name, lat, lon, trip_day))
    conn.commit()
    conn.close()

def get_expenses():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY trip_day ASC, expense_date ASC, id ASC", conn)
    conn.close()
    return df

def delete_expense(exp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
    conn.commit()
    conn.close()

def add_wishlist_item(title, cat, cost, loc):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO wishlist (title, category, estimated_cost, location_name) VALUES (?, ?, ?, ?)", (title, cat, cost, loc))
    conn.commit()
    conn.close()

def get_wishlist():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM wishlist ORDER BY id DESC", conn)
    conn.close()
    return df

def delete_wishlist_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM wishlist WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# --- 3. Live FX, Geocoding & Open-Meteo Weather APIs ---
@st.cache_data(ttl=3600)
def fetch_live_rates(base="SGD"):
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("result") == "success":
            return data.get("rates", {}), "🟢 Live Online"
    except Exception:
        pass
    fallback = {
        "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "CNY": 5.38, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60, "VND": 19000.0,
        "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "🟠 Fallback Offline"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name or place_name.strip() == "":
        return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_os_v4")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        loc = geocode(place_name)
        if loc:
            return loc.latitude, loc.longitude
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=1800, show_spinner=False)
def get_live_weather(lat, lon):
    if not lat or not lon:
        return None
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation"
        res = requests.get(url, timeout=5).json()
        current = res.get("current", {})
        temp = current.get("temperature_2m", 0)
        humidity = current.get("relative_humidity_2m", 0)
        w_code = current.get("weather_code", 0)
        rain = current.get("precipitation", 0)
        
        condition = "☀️ Sunny / Clear"
        tip = "Great weather for outdoor exploration!"
        if w_code in [1, 2, 3]: 
            condition = "⛅ Partly Cloudy"
            tip = "Pleasant conditions for walking tours."
        elif w_code in [45, 48]: 
            condition = "🌫️ Foggy"
            tip = "Low visibility at scenic observation towers."
        elif w_code in [51, 61, 80]: 
            condition = "🌧️ Light Showers"
            tip = "Carry a compact umbrella or rain shell."
        elif w_code >= 63: 
            condition = "⛈️ Heavy Rain / Thunderstorm"
            tip = "Ideal time to explore museums, cafes, or shopping centers."
        
        if temp < 10: tip += " ❄️ Pack warm layers!"
        elif temp > 32: tip += " 🥤 Stay hydrated & seek shade!"

        return {
            "temp": temp,
            "humidity": humidity,
            "condition": condition,
            "wind": current.get("wind_speed_10m", 0),
            "rain": rain,
            "tip": tip
        }
    except Exception:
        return None

init_db()

# --- 4. Sidebar Controls & Global Configuration ---
with st.sidebar:
    st.markdown("<h2 class='font-brand'>🧭 Trip Control Deck</h2>", unsafe_allow_html=True)
    rates_dict, status_msg = fetch_live_rates("SGD")
    st.caption(f"FX Feeds: **{status_msg}**")

    popular_currencies = ["JPY", "MYR", "THB", "CNY", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Other"]
    selected_foreign = st.selectbox("Destination Currency", popular_currencies, index=0)
    foreign_curr = st.text_input("Custom Currency Code", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 1.0))
    rate = st.number_input(f"Exchange Rate (1 SGD = X {foreign_curr})", value=default_rate, format="%.4f")

    st.markdown("---")
    st.markdown("<h4 class='font-brand'>🎯 Trip Budget & Runway</h4>", unsafe_allow_html=True)
    total_budget_sgd = st.number_input("Total Budget (SGD)", value=3500.0, step=100.0)
    trip_days = st.number_input("Trip Duration (Days)", min_value=1, value=7, step=1)
    
    st.markdown("---")
    st.markdown("<h4 class='font-brand'>👥 Travel Tribe</h4>", unsafe_allow_html=True)
    members_str = st.text_input("Group Members", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

df = get_expenses()
total_spent_sgd = df["amount_home"].sum() if not df.empty else 0.0

# --- 5. Interactive Destination Radar & Hero ---
col_hero, col_radar = st.columns([1.8, 1.2])

with col_hero:
    st.markdown(f"""
    <div class="glass-card" style="border-left: 6px solid var(--accent-glow); height: 100%;">
        <div class="chip-pill">🇸🇬 SG BASE → {foreign_curr} TRIP</div>
        <h1 class="font-brand" style="margin: 8px 0 4px 0; font-size: 2.2rem; color: var(--text-primary);">Travel Companion OS</h1>
        <p style="color: var(--text-secondary); margin: 0; font-size: 0.95rem;">
            Dynamic route analytics, live weather telemetry, and automated pairwise group splitting.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_radar:
    # Interactive Search for Weather Radar
    radar_col1, radar_col2 = st.columns([2, 1])
    with radar_col1:
        custom_radar_city = st.text_input("📍 Radar Target City", value="Tokyo", label_visibility="collapsed")
    with radar_col2:
        if st.button("🛰️ Scan Radar", use_container_width=True):
            st.session_state.radar_city = custom_radar_city

    active_city = st.session_state.get("radar_city", custom_radar_city)
    r_lat, r_lon = geocode_place(active_city)
    
    if not r_lat:
        r_lat, r_lon, active_city = 35.6762, 139.6503, "Tokyo (Default)"

    weather = get_live_weather(r_lat, r_lon)
    if weather:
        st.markdown(f"""
        <div class="radar-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="radar-badge">LIVE RADAR • {active_city.upper()}</span>
                <span style="font-size: 0.85rem; font-weight: 600;">💨 {weather['wind']} km/h</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 10px;">
                <span style="font-size: 2.3rem; font-weight: 800; line-height: 1;">{weather['temp']}°C</span>
                <span style="font-size: 1.05rem; font-weight: 700;">{weather['condition']}</span>
            </div>
            <div style="margin-top: 8px; font-size: 0.82rem; background: rgba(0,0,0,0.15); padding: 6px 10px; border-radius: 8px;">
                💡 <b>Trip Insight:</b> {weather['tip']}
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- 6. Main Feature Navigation Tabs ---
tab_timeline, tab_map, tab_wishlist, tab_fx, tab_analytics, tab_log, tab_settle, tab_packing = st.tabs([
    "🗓️ Itinerary Feed",
    "🗺️ Interactive Route",
    "✨ Wishlist & Bucket List",
    "⚡ FX Simulator",
    "📈 Financial Runway",
    "➕ Log Expense",
    "🤝 PayNow & Settle",
    "🎒 Smart Packing"
])

# --- TAB 1: Visual Itinerary Timeline Feed ---
with tab_timeline:
    st.markdown("<h3 class='font-brand'>🗓️ Day-by-Day Timeline</h3>", unsafe_allow_html=True)
    if not df.empty:
        days_present = sorted(df["trip_day"].unique())
        for d in days_present:
            day_df = df[df["trip_day"] == d]
            day_total = day_df["amount_home"].sum()

            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin: 16px 0 8px 0;">
                <span class="chip-pill" style="font-size: 0.85rem; padding: 6px 14px;">DAY {d} SCHEDULE</span>
                <span style="font-weight: 700; color: var(--accent-glow);">${day_total:,.2f} SGD Spent</span>
            </div>
            """, unsafe_allow_html=True)

            for _, item in day_df.iterrows():
                loc_str = f"📍 {item['location_name']}" if item['location_name'] else "General Location"
                st.markdown(f"""
                <div class="glass-card" style="border-left: 4px solid var(--accent-glow);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="chip-pill">{item['category']}</span>
                            <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-top: 4px;">{item['description']}</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">
                                {loc_str} &nbsp;•&nbsp; 🗓️ {item['expense_date']} &nbsp;•&nbsp; Paid by <b>{item['paid_by']}</b>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.35rem; font-weight: 800; color: var(--accent-glow);">${item['amount_home']:,.2f} SGD</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">{item['amount_foreign']:,.0f} {item['currency']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No timeline items logged yet. Record your stops in the 'Log Expense' tab!")

# --- TAB 2: Filterable Map View ---
with tab_map:
    st.markdown("<h3 class='font-brand'>🗺️ Geographic Route & Pin Filters</h3>", unsafe_allow_html=True)
    map_data = df.dropna(subset=["latitude", "longitude"])
    
    if not map_data.empty:
        c_filter1, c_filter2 = st.columns(2)
        with c_filter1:
            all_categories = ["All Categories"] + list(map_data["category"].unique())
            selected_cat = st.selectbox("Filter Map by Category", all_categories)
        with c_filter2:
            show_routes = st.checkbox("Draw Flight / Walking Routes", value=True)

        filtered_map = map_data if selected_cat == "All Categories" else map_data[map_data["category"] == selected_cat]

        if not filtered_map.empty:
            center_lat, center_lon = filtered_map["latitude"].mean(), filtered_map["longitude"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

            points = []
            for _, row in filtered_map.iterrows():
                points.append([row["latitude"], row["longitude"]])
                popup_html = f"""
                <div style='font-family: sans-serif; min-width: 180px;'>
                    <b style='color: #0284c7; font-size: 14px;'>{row['description']}</b><br>
                    <b>Cost:</b> ${row['amount_home']:.2f} SGD<br>
                    <b>Day:</b> Day {row['trip_day']}<br>
                    <b>Paid by:</b> {row['paid_by']}
                </div>
                """
                folium.Marker(
                    [row["latitude"], row["longitude"]],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"Day {row['trip_day']}: {row['description']} (${row['amount_home']:.2f} SGD)",
                    icon=folium.Icon(color="info", icon="map-pin", prefix="fa")
                ).add_to(m)

            if show_routes and len(points) > 1:
                folium.PolyLine(points, color="#0284c7", weight=3.5, opacity=0.8, dash_array="6, 10").add_to(m)

            st_folium(m, width="100%", height=520)
        else:
            st.warning("No pins match the selected category filter.")
    else:
        st.info("Include location/venue names when logging expenses to plot your interactive route pins.")

# --- TAB 3: Wishlist & Bucket List Scratchpad ---
with tab_wishlist:
    st.markdown("<h3 class='font-brand'>✨ Places to Visit & Bucket List</h3>", unsafe_allow_html=True)
    st.caption("Plan bucket-list spots before you go. Convert them directly into logged expenses with one click!")

    with st.container():
        with st.form("wishlist_form", clear_on_submit=True):
            w_c1, w_c2, w_c3, w_c4 = st.columns([2, 1, 1, 1])
            with w_c1:
                w_title = st.text_input("Place / Activity Wishlist", placeholder="e.g. Universal Studios Express Pass")
            with w_c2:
                w_cat = st.selectbox("Category", ["Activities", "Food & Dining", "Shopping", "Transport", "Other"])
            with w_c3:
                w_cost = st.number_input(f"Est. Cost ({foreign_curr})", min_value=0.0, step=10.0)
            with w_c4:
                w_loc = st.text_input("City / Venue", placeholder="e.g. Osaka")
            
            w_submit = st.form_submit_button("➕ Add to Bucket List", use_container_width=True)
            if w_submit and w_title:
                add_wishlist_item(w_title, w_cat, w_cost, w_loc)
                st.toast(f"Added to wishlist: {w_title}", icon="🎯")
                st.rerun()

    wish_df = get_wishlist()
    if not wish_df.empty:
        for _, item in wish_df.iterrows():
            st.markdown(f"""
            <div class="glass-card" style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="chip-pill">{item['category']}</span>
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-top: 4px;">{item['title']}</div>
                    <div style="font-size: 0.82rem; color: var(--text-secondary);">📍 {item['location_name'] or 'Not specified'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.25rem; font-weight: 800; color: var(--accent-glow);">
                        ~${(item['estimated_cost']/rate if rate > 0 else 0):,.2f} SGD
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">{item['estimated_cost']:,.0f} {foreign_curr}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c_del1, c_del2 = st.columns([4, 1])
            with c_del2:
                if st.button("🗑️ Remove", key=f"del_wish_{item['id']}"):
                    delete_wishlist_item(item['id'])
                    st.rerun()
    else:
        st.info("Your wishlist is currently empty. Brainstorm spots above!")

# --- TAB 4: Live FX Matrix & Interactive Simulator ---
with tab_fx:
    st.markdown("<h3 class='font-brand'>⚡ Live Currency Simulator & Matrix</h3>", unsafe_allow_html=True)
    
    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        st.markdown(f"""
        <div class="glass-card">
            <h4 style="margin: 0 0 10px 0; color: var(--text-primary);">Interactive FX Slider</h4>
            <span style="font-size: 0.85rem; color: var(--text-secondary);">Drag to calculate real-time foreign cost to SGD:</span>
        </div>
        """, unsafe_allow_html=True)
        fx_slider = st.slider(f"Foreign Price in {foreign_curr}", min_value=0, max_value=50000, value=2500, step=50)
        sgd_val = fx_slider / rate if rate > 0 else 0.0
        
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; border-left: 5px solid var(--accent-glow);">
            <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase;">Equivalent Home Cost</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: var(--accent-glow);">${sgd_val:,.2f} SGD</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">Conversion base: 1 SGD = {rate} {foreign_curr}</div>
        </div>
        """, unsafe_allow_html=True)

    with sim_col2:
        st.markdown("<h4 class='font-brand'>Popular Currency Matrix (per 1 SGD)</h4>", unsafe_allow_html=True)
        matrix_data = []
        for curr_code, curr_rate in rates_dict.items():
            if curr_code in ["JPY", "MYR", "THB", "CNY", "KRW", "TWD", "USD", "EUR", "GBP", "AUD"]:
                matrix_data.append({
                    "Currency": curr_code,
                    "Rate (1 SGD =)": f"{curr_rate:,.2f} {curr_code}",
                    "$100 SGD Worth": f"{(100 * curr_rate):,.2f} {curr_code}"
                })
        st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

# --- TAB 5: Burn Rate & Financial Telemetry ---
with tab_analytics:
    st.markdown("<h3 class='font-brand'>📈 Burn Rate & Budget Runway</h3>", unsafe_allow_html=True)
    remaining_budget = total_budget_sgd - total_spent_sgd
    pct_spent = min(100.0, (total_spent_sgd / total_budget_sgd * 100.0)) if total_budget_sgd > 0 else 0.0

    b1, b2, b3 = st.columns(3)
    b1.metric("Budget Remaining", f"${remaining_budget:,.2f} SGD", f"{100 - pct_spent:.1f}% left")
    b2.metric("Total Spent", f"${total_spent_sgd:,.2f} SGD")
    daily_allowance = remaining_budget / trip_days if trip_days > 0 else 0.0
    b3.metric("Safe Daily Allowance", f"${daily_allowance:,.2f} SGD/day")

    st.progress(pct_spent / 100.0)

    if not df.empty:
        c_left, c_right = st.columns(2)
        with c_left:
            st.subheader("Category Distribution")
            cat_totals = df.groupby("category")["amount_home"].sum()
            st.bar_chart(cat_totals, color="#0284c7")
        with c_right:
            st.subheader("Daily Spending Trajectory")
            day_totals = df.groupby("trip_day")["amount_home"].sum()
            st.line_chart(day_totals, color="#38bdf8")

        # CSV Export Generator
        st.markdown("---")
        st.markdown("<h4 class='font-brand'>📥 Export Ledger</h4>", unsafe_allow_html=True)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Complete Trip CSV",
            data=csv_buffer.getvalue(),
            file_name=f"trip_ledger_{date.today()}.csv",
            mime="text/csv"
        )

# --- TAB 6: Log Expense & Action Form ---
with tab_log:
    st.markdown("<h3 class='font-brand'>➕ Record New Transaction</h3>", unsafe_allow_html=True)
    with st.form("modern_logger_v2", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            desc = st.text_input("Activity / Item*", placeholder="e.g., Shibuya Sky Rooftop Ticket")
            amt = st.number_input(f"Cost in {foreign_curr}*", min_value=0.0, step=10.0)
            category = st.selectbox("Category", ["Food & Dining", "Transport", "Activities", "Accommodation", "Shopping", "Nightlife", "Other"])
            loc = st.text_input("City / Location Name (Optional)", placeholder="e.g., Shibuya Sky, Tokyo")
        with c2:
            t_day = st.number_input("Trip Day #", min_value=1, value=1, step=1)
            payer = st.selectbox("Paid By", members if members else ["Me"])
            exp_date = st.date_input("Date", value=date.today())
            st.caption(f"Estimated Conversion: **{(amt/rate if rate > 0 else 0):,.2f} SGD**")

        submit = st.form_submit_button("💾 Save Activity", use_container_width=True)
        if submit:
            if desc and amt > 0:
                lat, lon = geocode_place(loc)
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), loc, lat, lon, t_day)
                st.toast(f"Successfully recorded: {desc}", icon="🎉")
                st.rerun()
            else:
                st.error("Please provide both a description and an amount.")

    with st.expander("🗑️ Delete a Transaction"):
        if not df.empty:
            del_id = st.selectbox("Pick Entry to Delete", df["id"].tolist(), format_func=lambda x: f"ID #{x} - {df[df['id']==x]['description'].values[0]}")
            if st.button("Delete Permanently"):
                delete_expense(del_id)
                st.rerun()

# --- TAB 7: PayNow Settlement Engine ---
with tab_settle:
    st.markdown("<h3 class='font-brand'>🤝 Group PayNow Settlement Engine</h3>", unsafe_allow_html=True)
    if not df.empty and members:
        fair_share = total_spent_sgd / len(members)
        paid_map = df.groupby("paid_by")["amount_home"].sum().to_dict()
        balances = {m: paid_map.get(m, 0.0) - fair_share for m in members}

        debtors = [[m, -bal] for m, bal in balances.items() if bal < -0.01]
        creditors = [[m, bal] for m, bal in balances.items() if bal > 0.01]

        trans = []
        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            d_name, d_amt = debtors[i]
            c_name, c_amt = creditors[j]
            settle_val = min(d_amt, c_amt)
            trans.append((d_name, c_name, settle_val))
            debtors[i][1] -= settle_val
            creditors[j][1] -= settle_val
            if debtors[i][1] <= 0.001: i += 1
            if creditors[j][1] <= 0.001: j += 1

        if trans:
            st.markdown("#### Direct Settle Actions")
            for debtor, creditor, val in trans:
                st.markdown(f"""
                <div class="glass-card" style="border-left: 5px solid #10b981; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">👉 <b>{debtor}</b> pays <b>{creditor}</b></div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">Direct settlement via PayNow / FAST Transfer</div>
                    </div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: #10b981;">${val:,.2f} SGD</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("🎉 All accounts are balanced! No transfers required.")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")

# --- TAB 8: Dynamic Packing Checklist ---
with tab_packing:
    st.markdown("<h3 class='font-brand'>🎒 Smart Travel Packing Checklist</h3>", unsafe_allow_html=True)

    if "custom_packing" not in st.session_state:
        st.session_state.custom_packing = [
            {"name": "Passport & Flight Tickets", "done": True},
            {"name": "Universal Adapter & 65W GaN Charger", "done": False},
            {"name": "Multi-Currency Debit Card (YouTrip / Wise)", "done": True},
            {"name": "Noise Cancelling Earbuds", "done": False},
            {"name": "Emergency Medication / Band-Aids", "done": False},
            {"name": "Foldable Rain Jacket / Umbrella", "done": False}
        ]

    # Add new item input
    pack_c1, pack_c2 = st.columns([3, 1])
    with pack_c1:
        new_item = st.text_input("Add Custom Gear Item", placeholder="e.g. GoPro Hero 12 + Extra Batteries", label_visibility="collapsed")
    with pack_c2:
        if st.button("➕ Add Item", use_container_width=True) and new_item:
            st.session_state.custom_packing.append({"name": new_item, "done": False})
            st.rerun()

    total_p = len(st.session_state.custom_packing)
    done_p = sum(1 for x in st.session_state.custom_packing if x["done"])
    st.progress(done_p / total_p if total_p > 0 else 0)
    st.caption(f"Packed **{done_p} of {total_p}** items ({done_p/total_p*100:.0f}%)")

    for idx, item in enumerate(st.session_state.custom_packing):
        checked = st.checkbox(item["name"], value=item["done"], key=f"pack_check_{idx}")
        st.session_state.custom_packing[idx]["done"] = checked
