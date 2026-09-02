import streamlit as st
import pandas as pd
import requests
import pydeck as pdk
import re
import libsql_client
from datetime import date, datetime, timedelta

# ==============================================================================
# 1. TURSO CLOUD DATABASE SETUP & ENGINE (HTTPS PROTOCOL)
# ==============================================================================
DEFAULT_TURSO_URL = "https://travel-companion-fishindaocean.aws-ap-northeast-1.turso.io"
DEFAULT_TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJnaWQiOiI1OTJiZGY5NS1kOWEwLTQ5MDEtYTdlYS0xNWYyN2NlODU1NTMiLCJpYXQiOjE3ODgzNjU5NDksImtpZCI6IkkxX201Nmdtckg1OFhJZzZrRG1KT0VzT19zbDdjZmlfMjk1Y3RVekRNdWsiLCJyaWQiOiIyMzYzZmQ1ZC1jYjRhLTQwN2UtYmExOS1lYmUzZmY2NmM4MTgifQ.2o5ILQ7zJe4UPZtnPZLJv4CtRqjof4WxDFfhHaG5mrCmQHbVr2usTq4E2bGEYpOpyivAriLWID2f4VdySUzWDQ"

def get_db_client():
    url = st.secrets.get("TURSO_DB_URL", DEFAULT_TURSO_URL)
    # Streamlit Cloud blocks outbound WebSockets; force HTTPS protocol
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://", 1)
        
    token = st.secrets.get("TURSO_AUTH_TOKEN", DEFAULT_TURSO_TOKEN)
    return libsql_client.create_client_sync(url=url, auth_token=token)

@st.cache_resource
def init_db():
    client = get_db_client()
    
    # 1. Expenses Table
    client.execute("""
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
            latitude REAL DEFAULT 31.2304,
            longitude REAL DEFAULT 121.4737,
            split_with TEXT DEFAULT 'ALL'
        )
    """)
    
    # 2. Itinerary Table
    client.execute("""
        CREATE TABLE IF NOT EXISTS itinerary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_tag TEXT DEFAULT 'Day 1',
            time_str TEXT DEFAULT '12:00',
            place_name TEXT DEFAULT '',
            category TEXT DEFAULT 'Sightseeing',
            notes TEXT DEFAULT '',
            cost_foreign REAL DEFAULT 0.0,
            latitude REAL DEFAULT 31.2304,
            longitude REAL DEFAULT 121.4737,
            is_completed INTEGER DEFAULT 0
        )
    """)
    
    # 3. Packing & Checklist Table
    client.execute("""
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT DEFAULT '',
            category TEXT DEFAULT 'General',
            is_done INTEGER DEFAULT 0
        )
    """)
    
    # 4. Trip Settings Table
    client.execute("""
        CREATE TABLE IF NOT EXISTS trip_settings (
            id INTEGER PRIMARY KEY,
            trip_title TEXT,
            origin_city TEXT,
            origin_lat REAL,
            origin_lon REAL,
            start_date TEXT,
            end_date TEXT,
            budget_sgd REAL,
            members TEXT
        )
    """)
    client.close()
    return True

# Initialize database once on app launch
init_db()

# ==============================================================================
# 2. DATABASE REPOSITORY FUNCTIONS (TURSO CLOUD)
# ==============================================================================
def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date, lat, lon, split_with):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    client = get_db_client()
    client.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date, latitude, longitude, split_with)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date, lat, lon, split_with])
    client.close()

def get_expenses():
    client = get_db_client()
    res = client.execute("SELECT * FROM expenses ORDER BY id DESC")
    cols = res.columns
    rows = list(res.rows)
    client.close()
    if rows:
        return pd.DataFrame(rows, columns=cols)
    return pd.DataFrame(columns=[
        "id", "description", "amount_foreign", "currency", "exchange_rate",
        "amount_home", "paid_by", "category", "expense_date", "latitude", "longitude", "split_with"
    ])

def delete_expense(exp_id):
    client = get_db_client()
    client.execute("DELETE FROM expenses WHERE id = ?", [exp_id])
    client.close()

def get_checklist():
    client = get_db_client()
    res = client.execute("SELECT * FROM checklist ORDER BY id ASC")
    cols = res.columns
    rows = list(res.rows)
    client.close()
    if rows:
        return pd.DataFrame(rows, columns=cols)
    return pd.DataFrame(columns=["id", "item", "category", "is_done"])

def add_checklist_item(item, category):
    client = get_db_client()
    client.execute("INSERT INTO checklist (item, category, is_done) VALUES (?, ?, 0)", [item, category])
    client.close()

def toggle_checklist_item(item_id, is_done):
    client = get_db_client()
    client.execute("UPDATE checklist SET is_done = ? WHERE id = ?", [1 if is_done else 0, item_id])
    client.close()

def delete_checklist_item(item_id):
    client = get_db_client()
    client.execute("DELETE FROM checklist WHERE id = ?", [item_id])
    client.close()

def get_itinerary():
    client = get_db_client()
    res = client.execute("SELECT * FROM itinerary ORDER BY day_tag ASC, time_str ASC")
    cols = res.columns
    rows = list(res.rows)
    client.close()
    if rows:
        return pd.DataFrame(rows, columns=cols)
    return pd.DataFrame(columns=[
        "id", "day_tag", "time_str", "place_name", "category", "notes",
        "cost_foreign", "latitude", "longitude", "is_completed"
    ])

def add_itinerary_item(day_tag, time_str, place_name, category, notes, cost_foreign, lat, lon):
    client = get_db_client()
    client.execute("""
        INSERT INTO itinerary (day_tag, time_str, place_name, category, notes, cost_foreign, latitude, longitude, is_completed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, [day_tag, time_str, place_name, category, notes, cost_foreign, lat, lon])
    client.close()

def delete_itinerary_item(item_id):
    client = get_db_client()
    client.execute("DELETE FROM itinerary WHERE id = ?", [item_id])
    client.close()

def get_trip_settings():
    client = get_db_client()
    res = client.execute("SELECT trip_title, origin_city, origin_lat, origin_lon, start_date, end_date, budget_sgd, members FROM trip_settings WHERE id = 1")
    rows = list(res.rows)
    client.close()
    if rows:
        row = rows[0]
        return {
            "title": row[0],
            "origin_city": row[1],
            "origin_lat": float(row[2]),
            "origin_lon": float(row[3]),
            "start_date": datetime.strptime(row[4], "%Y-%m-%d").date(),
            "end_date": datetime.strptime(row[5], "%Y-%m-%d").date(),
            "budget": float(row[6]),
            "members": row[7]
        }
    return {
        "title": "East Asia Grand Tour 2026",
        "origin_city": "Singapore (Changi SIN)",
        "origin_lat": 1.3644,
        "origin_lon": 103.9915,
        "start_date": date.today(),
        "end_date": date.today() + timedelta(days=9),
        "budget": 4500.0,
        "members": "Sen Yuan, Alex, Jordan"
    }

def save_trip_settings(title, origin_city, origin_lat, origin_lon, start_date_str, end_date_str, budget, members):
    client = get_db_client()
    client.execute("""
        INSERT OR REPLACE INTO trip_settings (id, trip_title, origin_city, origin_lat, origin_lon, start_date, end_date, budget_sgd, members)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [title, origin_city, origin_lat, origin_lon, start_date_str, end_date_str, budget, members])
    client.close()

# ==============================================================================
# 3. LIVE EXTERNAL APIS (FOREX & ZERO-KEY OPEN-METEO WEATHER)
# ==============================================================================
@st.cache_data(ttl=3600)
def fetch_live_rates(base="SGD"):
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("result") == "success":
            return data.get("rates", {}), "● Live Sync"
    except Exception:
        pass
    fallback = {
        "CNY": 5.40, "MYR": 3.48, "JPY": 115.0, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60,
        "VND": 19000.0, "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "○ Offline Rates"

@st.cache_data(ttl=1800)
def fetch_live_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto"
    try:
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            curr = data.get("current", {})
            w_code = curr.get("weather_code", 0)
            
            condition = "Clear Sky"
            icon = "☀️"
            if w_code in [1, 2, 3]:
                condition = "Partly Cloudy"
                icon = "⛅"
            elif w_code in [45, 48]:
                condition = "Foggy"
                icon = "🌫️"
            elif w_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                condition = "Showers & Rain"
                icon = "🌧️"
            elif w_code in [71, 73, 75, 85, 86]:
                condition = "Snow"
                icon = "❄️"
            elif w_code >= 95:
                condition = "Thunderstorm"
                icon = "⛈️"
                
            return {
                "temp": f"{curr.get('temperature_2m', '--')}°C",
                "humidity": f"{curr.get('relative_humidity_2m', '--')}%",
                "wind": f"{curr.get('wind_speed_10m', '--')} km/h",
                "condition": condition,
                "icon": icon,
                "status": "Live Radar Operational"
            }
    except Exception:
        pass
    return {
        "temp": "22.5°C", "humidity": "64%", "wind": "12 km/h",
        "condition": "Mild Weather", "icon": "🌤️", "status": "Simulated Atmosphere"
    }

# ==============================================================================
# 4. PRESETS & SEEDING ENGINE
# ==============================================================================
CITY_PRESETS = {
    "Shanghai, China": (31.2304, 121.4737, "CNY"),
    "Beijing, China": (39.9042, 116.4074, "CNY"),
    "Shenzhen, China": (22.5431, 114.0579, "CNY"),
    "Hangzhou, China": (30.2741, 120.1551, "CNY"),
    "Tokyo, Japan": (35.6762, 139.6503, "JPY"),
    "Kuala Lumpur, Malaysia": (3.1390, 101.6869, "MYR"),
    "Johor Bahru, Malaysia": (1.4927, 103.7414, "MYR"),
    "Seoul, South Korea": (37.5665, 126.9780, "KRW"),
    "Bangkok, Thailand": (13.7563, 100.5018, "THB"),
    "Custom Coordinates": (0.0, 0.0, "USD")
}

def seed_demo_data():
    if get_checklist().empty:
        add_checklist_item("Passport (valid min. 6 months) & Visa Documents", "Essentials")
        add_checklist_item("Alipay & WeChat Pay backed by SGD Cards", "Finance")
        add_checklist_item("High-Speed Rail 12306 Verified Account", "Transit")
        add_checklist_item("Universal Multi-plug Travel Adapter", "Electronics")
        add_checklist_item("Unlimited Roaming eSIM / Cross-border VPN", "Tech")

    if get_itinerary().empty:
        add_itinerary_item("Day 1 • Arrival & The Bund", "10:30", "Yu Garden & Huxinting Tea House", "Culture", "Traditional soup dumplings & tea tasting", 160.0, 31.2272, 121.4921)
        add_itinerary_item("Day 1 • Arrival & The Bund", "16:00", "The Bund Historic Promenade", "Sightseeing", "Golden hour architecture stroll", 0.0, 31.2400, 121.4900)
        add_itinerary_item("Day 1 • Arrival & The Bund", "19:45", "Lujiazui Shanghai Tower Observatory", "Attraction", "Top deck panoramic night view", 380.0, 31.2335, 121.5056)
        add_itinerary_item("Day 2 • French Concession", "11:00", "Wukang Road Architecture & Cafes", "Dining", "Specialty espresso & artisan bakery", 95.0, 31.2078, 121.4428)

    if get_expenses().empty:
        log_expense("Maglev Train Airport Express", 100.0, "CNY", 5.40, "Sen Yuan", "Transport", str(date.today()), 31.1443, 121.8083, "ALL")
        log_expense("Welcome Feast at Haidilao", 420.0, "CNY", 5.40, "Alex", "Food & Dining", str(date.today()), 31.2304, 121.4737, "ALL")
        log_expense("Shanghai Tower Observation Tickets", 540.0, "CNY", 5.40, "Sen Yuan", "Activities", str(date.today()), 31.2335, 121.5056, "ALL")

seed_demo_data()

# ==============================================================================
# 5. STREAMLIT CONFIG & CYBER-LUXURY UI STYLING
# ==============================================================================
st.set_page_config(
    page_title="Vanguard OS — Elite Travel Companion",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --bg: #07090E;
        --card-bg: rgba(14, 18, 27, 0.72);
        --card-solid: #0F131D;
        --card-border: rgba(255, 255, 255, 0.07);
        --card-border-glow: rgba(226, 184, 87, 0.35);
        --gold: #E2B857;
        --gold-glow: rgba(226, 184, 87, 0.18);
        --cyan: #06B6D4;
        --emerald: #10B981;
        --rose: #F43F5E;
        --text-pure: #FFFFFF;
        --text-sub: #94A3B8;
        --text-dim: #64748B;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: var(--bg) !important;
        color: var(--text-pure) !important;
    }

    header[data-testid="stHeader"] { background: transparent !important; }
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1480px !important;
    }
    footer, #MainMenu { visibility: hidden !important; }

    @keyframes pulse-glow {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
        70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .status-ping {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: var(--emerald);
        display: inline-block;
        animation: pulse-glow 2s infinite;
    }

    .v-card {
        background: var(--card-bg);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 18px;
        transition: border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .v-card:hover {
        border-color: rgba(255, 255, 255, 0.15);
    }

    .command-ribbon {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 24px;
        background: linear-gradient(135deg, rgba(20, 26, 38, 0.85) 0%, rgba(10, 13, 20, 0.9) 100%);
        backdrop-filter: blur(28px);
        border: 1px solid rgba(226, 184, 87, 0.22);
        border-radius: 18px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
        margin-bottom: 22px;
    }
    .command-title {
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text-pure);
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .badge-gold {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 600;
        color: var(--gold);
        background: rgba(226, 184, 87, 0.1);
        border: 1px solid rgba(226, 184, 87, 0.3);
        padding: 5px 12px;
        border-radius: 9999px;
    }

    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 14px;
        margin-bottom: 24px;
    }
    .kpi-tile {
        background: rgba(18, 24, 37, 0.55);
        backdrop-filter: blur(16px);
        border: 1px solid var(--card-border);
        border-radius: 14px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
    }
    .kpi-tile::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-dim);
    }
    .kpi-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 700;
        color: var(--text-pure);
        margin-top: 6px;
    }

    .weather-pod {
        display: flex;
        align-items: center;
        gap: 12px;
        background: rgba(6, 182, 212, 0.08);
        border: 1px solid rgba(6, 182, 212, 0.25);
        border-radius: 12px;
        padding: 8px 16px;
    }

    .timeline-card {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        background: rgba(18, 23, 35, 0.6);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .timeline-card:hover {
        transform: translateX(4px);
        border-color: var(--gold-glow);
    }

    div.stButton > button {
        background: linear-gradient(135deg, #E2B857 0%, #C99E38 100%) !important;
        color: #07090E !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 10px 24px !important;
        box-shadow: 0 4px 18px var(--gold-glow) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 24px rgba(226, 184, 87, 0.4) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: rgba(15, 19, 30, 0.6);
        padding: 8px;
        border-radius: 14px;
        border: 1px solid var(--card-border);
        margin-bottom: 22px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 10px;
        color: var(--text-sub);
        font-weight: 600;
        font-size: 13.5px;
        padding: 0 20px;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.09) !important;
        color: var(--gold) !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 6. SIDEBAR FLIGHT CONTROLLER
# ==============================================================================
rates_dict, sync_status = fetch_live_rates("SGD")
current_settings = get_trip_settings()

with st.sidebar:
    st.markdown("### 🛰️ Mission Parameters")
    trip_title = st.text_input("Expedition Title", value=current_settings["title"])

    c_s1, c_s2 = st.columns(2)
    s_date = c_s1.date_input("Departure", value=current_settings["start_date"])
    e_date = c_s2.date_input("Return", value=current_settings["end_date"])
    if e_date < s_date:
        e_date = s_date

    total_days = (e_date - s_date).days + 1
    total_nights = max(0, total_days - 1)

    st.markdown("---")
    st.markdown("### 💱 Currency Exchange Terminal")
    st.caption(f"Sync Engine: **{sync_status}** (Auto Refresh 1h)")

    home_curr = "SGD"
    currencies_catalog = ["CNY", "MYR", "JPY", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Custom"]
    selected_foreign = st.selectbox("Primary Destination Currency", currencies_catalog, index=0)

    if selected_foreign == "Custom":
        foreign_curr = st.text_input("Custom ISO Code (e.g. CHF, AED)", value="HKD").upper()
    else:
        foreign_curr = selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 5.40))
    rate = st.number_input(f"Exchange Rate (1 {home_curr} = X {foreign_curr})", value=default_rate, format="%.4f")

    st.markdown("---")
    st.markdown("### 🎯 Treasury & Group")
    total_budget_sgd = st.number_input("Target Budget (SGD)", min_value=100.0, value=float(current_settings["budget"]), step=500.0)
    members_raw = st.text_input("Group Roster (comma-separated)", value=current_settings["members"])
    members_list = [m.strip() for m in members_raw.split(",") if m.strip()]
    if not members_list:
        members_list = ["Sen Yuan"]

    if (trip_title != current_settings["title"] or s_date != current_settings["start_date"] or 
        e_date != current_settings["end_date"] or total_budget_sgd != current_settings["budget"] or 
        members_raw != current_settings["members"]):
        save_trip_settings(
            trip_title, current_settings["origin_city"], current_settings["origin_lat"],
            current_settings["origin_lon"], str(s_date), str(e_date), total_budget_sgd, members_raw
        )

    st.markdown("---")
    st.markdown("### ⚡ Live Forex Quick-Math")
    quick_foreign = st.number_input(f"Amount ({foreign_curr})", value=200.0, step=50.0)
    quick_sgd = quick_foreign / rate if rate > 0 else 0.0
    st.markdown(f"""
    <div style="background: rgba(226, 184, 87, 0.08); border: 1px solid rgba(226, 184, 87, 0.3); border-radius: 10px; padding: 12px; text-align: center;">
        <div style="font-size: 11px; text-transform: uppercase; color: #94A3B8;">Converted Home Cost</div>
        <div style="font-family: 'JetBrains Mono'; font-size: 20px; font-weight: 700; color: #E2B857; margin-top: 2px;">
            S${quick_sgd:,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 7. METRICS & BUDGET RUNWAY ENGINE
# ==============================================================================
df_expenses = get_expenses()
df_checklist = get_checklist()
df_itinerary = get_itinerary()

total_foreign_spent = df_expenses["amount_foreign"].sum() if not df_expenses.empty else 0.0
total_sgd_spent = df_expenses["amount_home"].sum() if not df_expenses.empty else 0.0
remaining_sgd = total_budget_sgd - total_sgd_spent
burn_rate_pct = min(100.0, (total_sgd_spent / total_budget_sgd * 100.0)) if total_budget_sgd > 0 else 0.0

today_val = date.today()
if today_val < s_date:
    days_left_until_trip = (s_date - today_val).days
    mission_status = f"T-minus {days_left_until_trip} Days"
    remaining_days = total_days
elif today_val > e_date:
    mission_status = "Expedition Complete"
    remaining_days = 1
else:
    active_day = (today_val - s_date).days + 1
    mission_status = f"Day {active_day} of {total_days}"
    remaining_days = max(1, (e_date - today_val).days + 1)

daily_burn_velocity = total_sgd_spent / (total_days - remaining_days + 1) if (total_days - remaining_days + 1) > 0 else total_sgd_spent
safe_daily_runway = max(0.0, remaining_sgd / remaining_days)

default_dest_lat, default_dest_lon = 31.2304, 121.4737
if not df_itinerary.empty and pd.notnull(df_itinerary["latitude"].iloc[0]):
    default_dest_lat = float(df_itinerary["latitude"].iloc[0])
    default_dest_lon = float(df_itinerary["longitude"].iloc[0])

weather_data = fetch_live_weather(default_dest_lat, default_dest_lon)

# ==============================================================================
# 8. TOP CYBER COMMAND RIBBON & KPI DECK
# ==============================================================================
st.markdown(f"""
<div class="command-ribbon">
    <div class="command-title">
        <span class="status-ping"></span>
        <span>{trip_title}</span>
        <span style="font-size: 13px; font-weight: 500; color: #64748B;">|&nbsp; {total_days}D / {total_nights}N ({s_date.strftime('%b %d')} – {e_date.strftime('%b %d')})</span>
    </div>
    <div style="display: flex; align-items: center; gap: 14px;">
        <div class="weather-pod">
            <span style="font-size: 18px;">{weather_data['icon']}</span>
            <div>
                <div style="font-size: 12px; font-weight: 600; color: #E2E8F0;">{weather_data['temp']} • {weather_data['condition']}</div>
                <div style="font-size: 10px; color: #06B6D4; font-family: 'JetBrains Mono';">Hum: {weather_data['humidity']} | Wind: {weather_data['wind']}</div>
            </div>
        </div>
        <div class="badge-gold">1 SGD ≈ {rate:.2f} {foreign_curr}</div>
        <div style="font-family: 'JetBrains Mono'; font-size: 12px; font-weight: 600; background: rgba(255,255,255,0.06); padding: 6px 12px; border-radius: 8px;">
            {mission_status}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-tile">
        <div class="kpi-label">Allocated Budget</div>
        <div class="kpi-val">S${total_budget_sgd:,.2f}</div>
        <div style="font-size: 11px; color: #64748B; margin-top: 4px;">Baseline Cap</div>
    </div>
    <div class="kpi-tile">
        <div class="kpi-label">Aggregated Burn</div>
        <div class="kpi-val" style="color: #E2B857;">S${total_sgd_spent:,.2f}</div>
        <div style="font-size: 11px; color: #E2B857; margin-top: 4px;">{burn_rate_pct:.1f}% Budget Consumed</div>
    </div>
    <div class="kpi-tile">
        <div class="kpi-label">Remaining Runway</div>
        <div class="kpi-val" style="color: {'#10B981' if remaining_sgd >= 0 else '#F43F5E'};">S${remaining_sgd:,.2f}</div>
        <div style="font-size: 11px; color: {'#10B981' if remaining_sgd >= 0 else '#F43F5E'}; margin-top: 4px;">
            {'Surplus Active' if remaining_sgd >= 0 else 'Deficit Alert'}
        </div>
    </div>
    <div class="kpi-tile">
        <div class="kpi-label">Safe Daily Velocity</div>
        <div class="kpi-val" style="color: #06B6D4;">S${safe_daily_runway:,.2f}</div>
        <div style="font-size: 11px; color: #64748B; margin-top: 4px;">For {remaining_days} remaining day(s)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 9. WORKSPACE TABS INTERFACE
# ==============================================================================
tab_log, tab_intel, tab_geo, tab_split, tab_planner, tab_vault = st.tabs([
    "⚡ Quick Add & AI Parser",
    "📊 Financial Velocity & Ledger",
    "🌐 3D Arc & Vector Geospatial",
    "🤝 Optimal Debt Settlement",
    "🗺️ Dynamic Day Matrix",
    "🛡️ Packing & Secret Vault"
])

# ------------------------------------------------------------------------------
# TAB 1: QUICK ADD & NATURAL LANGUAGE PARSER
# ------------------------------------------------------------------------------
with tab_log:
    col_input1, col_input2 = st.columns([1.1, 1], gap="large")

    with col_input1:
        st.markdown("#### ⚡ Natural Language Quick Logger")
        st.caption("Paste receipt text or short phrases: e.g., `180 CNY Hotpot at Bund with Alex`")
        
        nlp_text = st.text_area("Quick Command Bar", placeholder="Type e.g., 250 CNY Dinner with Alex and Sen Yuan", height=90)
        
        parsed_amt = 0.0
        parsed_curr = foreign_curr
        parsed_desc = ""
        
        if nlp_text:
            amt_match = re.search(r"(\d+(?:\.\d{1,2})?)", nlp_text)
            curr_match = re.search(r"(CNY|SGD|JPY|MYR|USD|EUR|KRW|THB|TWD)", nlp_text, re.IGNORECASE)
            if amt_match:
                parsed_amt = float(amt_match.group(1))
            if curr_match:
                parsed_curr = curr_match.group(1).upper()
            parsed_desc = nlp_text.strip()

        with st.form("structured_expense_form", clear_on_submit=True):
            f_desc = st.text_input("Expense Description", value=parsed_desc if parsed_desc else "")
            
            c_f1, c_f2 = st.columns(2)
            f_amt = c_f1.number_input(f"Amount ({parsed_curr})", min_value=0.0, value=parsed_amt if parsed_amt > 0 else 80.0, step=10.0)
            f_cat = c_f2.selectbox("Classification", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Tech & eSIM", "Emergency", "Other"])
            
            c_p1, c_p2 = st.columns(2)
            f_payer = c_p1.selectbox("Payer", members_list)
            f_date = c_p2.date_input("Timestamp", value=date.today())
            
            f_city_preset = st.selectbox("Location Tag (For 3D Coordinates)", list(CITY_PRESETS.keys()), index=0)
            if f_city_preset == "Custom Coordinates":
                c_la, c_lo = st.columns(2)
                f_lat = c_la.number_input("Latitude", value=31.2304, format="%.4f")
                f_lon = c_lo.number_input("Longitude", value=121.4737, format="%.4f")
            else:
                f_lat, f_lon, _ = CITY_PRESETS[f_city_preset]

            f_split_strategy = st.radio("Debt Allocation", ["Split Across Entire Group", "Specific Members Only"], horizontal=True)
            if f_split_strategy == "Specific Members Only":
                chosen_members = st.multiselect("Select Debtors", members_list, default=members_list)
                f_split_str = ",".join(chosen_members) if chosen_members else "ALL"
            else:
                f_split_str = "ALL"

            sgd_calc = f_amt / rate if rate > 0 else 0.0
            st.info(f"Target Value: **S${sgd_calc:,.2f} SGD** (Exchange Rate: 1 SGD = {rate} {parsed_curr})")

            if st.form_submit_button("Commit Entry to Database", use_container_width=True):
                if f_amt > 0:
                    desc_to_save = f_desc.strip() if f_desc.strip() else f"{f_cat} Expense"
                    log_expense(desc_to_save, f_amt, parsed_curr, rate, f_payer, f_cat, str(f_date), f_lat, f_lon, f_split_str)
                    st.success(f"✓ Stored: {desc_to_save}")
                    st.rerun()
                else:
                    st.warning("Please enter an amount greater than 0.")

    with col_input2:
        st.markdown("#### 💎 Instant Conversions Cheat Sheet")
        st.markdown(f"Quick-scan reference table using live rate **1 SGD = {rate:.3f} {foreign_curr}**")
        
        increments_sgd = [10, 25, 50, 100, 200, 500, 1000]
        ref_rows = []
        for s in increments_sgd:
            ref_rows.append({
                "SGD (Home)": f"S${s:,}",
                f"{foreign_curr} (Foreign)": f"{s * rate:,.2f} {foreign_curr}",
                "Rough Context": "Snacks / Metro" if s <= 25 else "Fine Dining" if s <= 100 else "Hotel / Attraction" if s <= 500 else "High Speed Rail / Luxury"
            })
        st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 2: LEDGER & FINANCIAL VELOCITY
# ------------------------------------------------------------------------------
with tab_intel:
    if not df_expenses.empty:
        col_l1, col_l2 = st.columns([1.3, 1], gap="large")

        with col_l1:
            st.markdown("#### Complete Expense Ledger")
            view_df = df_expenses[["id", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by", "split_with"]].copy()
            view_df = view_df.rename(columns={
                "id": "ID", "expense_date": "Date", "description": "Description", "category": "Category",
                "amount_foreign": f"Foreign ({foreign_curr})", "currency": "Curr", "amount_home": "SGD Equiv",
                "paid_by": "Payer", "split_with": "Split For"
            })
            view_df[f"Foreign ({foreign_curr})"] = view_df[f"Foreign ({foreign_curr})"].apply(lambda x: f"{x:,.2f}")
            view_df["SGD Equiv"] = view_df["SGD Equiv"].apply(lambda x: f"S${x:,.2f}")

            st.dataframe(view_df, use_container_width=True, hide_index=True)

            c_exp_btn, c_del_btn = st.columns(2)
            with c_exp_btn:
                csv_bytes = df_expenses.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Ledger (CSV)",
                    data=csv_bytes,
                    file_name=f"vanguard_ledger_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with c_del_btn:
                del_target = st.number_input("Delete Item by ID", min_value=1, step=1, key="del_exp_input")
                if st.button("Purge Entry", use_container_width=True):
                    delete_expense(del_target)
                    st.rerun()

        with col_l2:
            st.markdown("#### Sector Allocation")
            cat_df = df_expenses.groupby("category")["amount_home"].sum().reset_index()
            cat_df["Percent"] = (cat_df["amount_home"] / total_sgd_spent * 100).apply(lambda x: f"{x:.1f}%")
            cat_df["SGD Value"] = cat_df["amount_home"].apply(lambda x: f"S${x:,.2f}")

            st.bar_chart(data=cat_df.set_index("category")["amount_home"], color="#E2B857")

            st.markdown("#### Daily Cumulative Velocity (SGD)")
            daily_df = df_expenses.groupby("expense_date")["amount_home"].sum().reset_index()
            st.line_chart(data=daily_df.set_index("expense_date")["amount_home"], color="#06B6D4")
    else:
        st.info("No recorded transactions in database. Add an expense or seed data.")

# ------------------------------------------------------------------------------
# TAB 3: 3D ARCS & VECTOR GEOSPATIAL MAP
# ------------------------------------------------------------------------------
with tab_geo:
    st.markdown("#### 3D Great-Circle Flight Arcs & Geospatial Points")
    st.caption("Featuring interactive Great-Circle trajectory layers originating from Singapore Changi (SIN). Zero Mapbox Token required.")

    origin_lon, origin_lat = 103.9915, 1.3644

    dest_points = []
    arc_routes = []

    if not df_expenses.empty:
        for _, row in df_expenses.iterrows():
            if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                dest_points.append({
                    "name": row["description"],
                    "category": row["category"],
                    "subtitle": f"Expense: S${row['amount_home']:.2f} ({row['paid_by']})",
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "elevation": max(100.0, float(row["amount_home"]) * 10.0),
                    "color": [226, 184, 87, 230]
                })

    if not df_itinerary.empty:
        for _, row in df_itinerary.iterrows():
            if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                dest_points.append({
                    "name": row["place_name"],
                    "category": row["category"],
                    "subtitle": f"Itinerary: {row['day_tag']} @ {row['time_str']}",
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "elevation": 150.0,
                    "color": [6, 182, 212, 230]
                })

    unique_coords = set((p["lat"], p["lon"]) for p in dest_points)
    for (d_lat, d_lon) in unique_coords:
        arc_routes.append({
            "from_name": "Singapore Changi (SIN)",
            "to_name": "Destination Terminal",
            "from_coords": [origin_lon, origin_lat],
            "to_coords": [d_lon, d_lat]
        })

    df_points = pd.DataFrame(dest_points)
    df_arcs = pd.DataFrame(arc_routes)

    if not df_points.empty:
        column_layer = pdk.Layer(
            "ColumnLayer",
            data=df_points,
            get_position="[lon, lat]",
            get_elevation="elevation",
            elevation_scale=10,
            radius=250,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_points,
            get_position="[lon, lat]",
            get_color="color",
            get_radius=180,
            radius_min_pixels=6,
            radius_max_pixels=15,
            pickable=True,
        )

        arc_layer = pdk.Layer(
            "ArcLayer",
            data=df_arcs,
            get_source_position="from_coords",
            get_target_position="to_coords",
            get_source_color=[6, 182, 212, 180],
            get_target_color=[226, 184, 87, 240],
            get_width=3,
            pickable=True
        )

        view_state = pdk.ViewState(
            latitude=df_points["lat"].mean(),
            longitude=df_points["lon"].mean(),
            zoom=10.5,
            pitch=45,
            bearing=15
        )

        deck = pdk.Deck(
            layers=[arc_layer, column_layer, scatter_layer],
            initial_view_state=view_state,
            map_provider="carto",
            map_style="dark",
            tooltip={
                "html": "<b>{name}</b><br/>Category: {category}<br/>{subtitle}",
                "style": {"backgroundColor": "#0F131D", "color": "#FFFFFF", "borderRadius": "8px", "border": "1px solid rgba(255,255,255,0.1)"}
            }
        )
        st.pydeck_chart(deck, use_container_width=True)
    else:
        st.info("No spatial GPS markers logged yet.")

# ------------------------------------------------------------------------------
# TAB 4: OPTIMAL DEBT SETTLEMENT GRAPH
# ------------------------------------------------------------------------------
with tab_split:
    st.markdown("#### Optimal Peer-to-Peer Debt Resolution")
    st.caption("Greedy minimal transaction balance optimizer. Eliminates circular bank transfers.")

    if not df_expenses.empty and members_list:
        paid_balances = {m: 0.0 for m in members_list}
        consumed_balances = {m: 0.0 for m in members_list}

        for _, row in df_expenses.iterrows():
            cost = row["amount_home"]
            payer_guy = row["paid_by"]
            if payer_guy in paid_balances:
                paid_balances[payer_guy] += cost

            split_rule = str(row["split_with"])
            if split_rule == "ALL" or not split_rule:
                debtors = members_list
            else:
                debtors = [p.strip() for p in split_rule.split(",") if p.strip() in members_list]
                if not debtors:
                    debtors = members_list

            each_share = cost / len(debtors)
            for d in debtors:
                consumed_balances[d] += each_share

        col_st1, col_st2 = st.columns([1.2, 1], gap="large")

        with col_st1:
            st.markdown("##### Net Member Balances")
            net_overview = []
            debtors_heap = []
            creditors_heap = []

            for m in members_list:
                p_paid = paid_balances[m]
                p_consumed = consumed_balances[m]
                net = p_paid - p_consumed

                if net < -0.01:
                    debtors_heap.append([m, abs(net)])
                elif net > 0.01:
                    creditors_heap.append([m, net])

                net_overview.append({
                    "Member": m,
                    "Total Paid": f"S${p_paid:,.2f}",
                    "Consumed Share": f"S${p_consumed:,.2f}",
                    "Net Position": f"S${net:+,.2f}",
                    "Status": "✦ Receive Back" if net > 0.01 else "✦ Owes Money" if net < -0.01 else "✓ Clean / Zero"
                })

            st.dataframe(pd.DataFrame(net_overview), use_container_width=True, hide_index=True)

        with col_st2:
            st.markdown("##### Minimal Transfer Sequence")
            d_i, c_i = 0, 0
            steps = []

            while d_i < len(debtors_heap) and c_i < len(creditors_heap):
                debtor, debt_amt = debtors_heap[d_i]
                creditor, cred_amt = creditors_heap[c_i]

                tx_amt = min(debt_amt, cred_amt)
                tx_foreign = tx_amt * rate
                steps.append({
                    "from": debtor,
                    "to": creditor,
                    "sgd": tx_amt,
                    "foreign": tx_foreign
                })

                debtors_heap[d_i][1] -= tx_amt
                creditors_heap[c_i][1] -= tx_amt

                if debtors_heap[d_i][1] < 0.01:
                    d_i += 1
                if creditors_heap[c_i][1] < 0.01:
                    c_i += 1

            if steps:
                for step in steps:
                    st.markdown(f"""
                    <div style="background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 14px 18px; margin-bottom: 8px;">
                        <span style="font-weight: 600; color: #FFFFFF;">{step['from']}</span>
                        <span style="color: #94A3B8;">&nbsp;transfers to&nbsp;</span>
                        <span style="font-weight: 600; color: #FFFFFF;">{step['to']}</span>
                        <div style="font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 700; color: #10B981; margin-top: 4px;">
                            S${step['sgd']:,.2f} &nbsp;<span style="font-size: 12px; color: #94A3B8;">(~{step['foreign']:,.2f} {foreign_curr})</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("All accounts balanced! Zero transfers needed.")
    else:
        st.info("Log expenses to compute settlement matrix.")

# ------------------------------------------------------------------------------
# TAB 5: DYNAMIC DAY MATRIX ITINERARY
# ------------------------------------------------------------------------------
with tab_planner:
    st.markdown("#### Dynamic Expedition Itinerary")
    
    itin_days = [f"Day {idx+1} • {(s_date + timedelta(days=idx)).strftime('%a, %b %d')}" for idx in range(total_days)]
    
    col_it1, col_it2 = st.columns([1.3, 1], gap="large")
    
    with col_it1:
        if not df_itinerary.empty:
            existing_days_in_db = list(dict.fromkeys(df_itinerary["day_tag"].tolist()))
            combined_day_tags = list(dict.fromkeys(itin_days + existing_days_in_db))
            
            chosen_day = st.segmented_control("Select Active Schedule", combined_day_tags, default=combined_day_tags[0], label_visibility="collapsed")
            
            day_schedule = df_itinerary[df_itinerary["day_tag"] == chosen_day]
            if not day_schedule.empty:
                for _, item in day_schedule.iterrows():
                    cost_sgd = item['cost_foreign'] / rate if rate > 0 else 0.0
                    cost_label = f"{item['cost_foreign']:,.0f} {foreign_curr} (~S${cost_sgd:.1f})" if item['cost_foreign'] > 0 else "Free Activity"
                    
                    st.markdown(f"""
                    <div class="timeline-card">
                        <div style="font-family: 'JetBrains Mono'; font-size: 13px; font-weight: 700; color: #E2B857; min-width: 60px;">
                            {item['time_str']}
                        </div>
                        <div style="flex-grow: 1;">
                            <div style="font-size: 15px; font-weight: 600; color: #FFFFFF;">
                                {item['place_name']}
                                <span style="font-size: 10px; font-weight: 500; color: #64748B; border: 1px solid rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 6px; margin-left: 8px;">
                                    {item['category']}
                                </span>
                            </div>
                            <div style="font-size: 12px; color: #94A3B8; margin-top: 4px;">{item['notes']}</div>
                        </div>
                        <div style="font-family: 'JetBrains Mono'; font-size: 12px; font-weight: 600; color: #06B6D4;">
                            {cost_label}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(f"No itinerary stops logged for {chosen_day}.")

            del_it_id = st.number_input("Remove Stop ID", min_value=1, step=1, key="del_itin_box")
            if st.button("Delete Itinerary Item"):
                delete_itinerary_item(del_it_id)
                st.rerun()
        else:
            st.info("Itinerary schedule is currently unpopulated.")

    with col_it2:
        st.markdown("##### Schedule New Itinerary Stop")
        with st.form("new_itinerary_form", clear_on_submit=True):
            it_day = st.selectbox("Assign Day", itin_days)
            c_ih1, c_ih2 = st.columns(2)
            it_time = c_ih1.text_input("Time (24-Hour)", value="14:00")
            it_cat = c_ih2.selectbox("Type", ["Sightseeing", "Dining", "Culture", "Attraction", "Transit", "Shopping", "Nightlife"])
            it_place = st.text_input("Destination / Landmark", placeholder="e.g. Forbidden City / Shibuya Sky")
            it_notes = st.text_input("Operational Notes", placeholder="e.g. Fast-track tickets booked online")
            it_cost = st.number_input(f"Expected Foreign Cost ({foreign_curr})", min_value=0.0, value=0.0, step=20.0)

            it_preset = st.selectbox("Location Coordinates", list(CITY_PRESETS.keys()), index=0, key="itin_geo_preset")
            if it_preset == "Custom Coordinates":
                c_il1, c_il2 = st.columns(2)
                it_lat = c_il1.number_input("Lat", value=31.2304, format="%.4f")
                it_lon = c_il2.number_input("Lon", value=121.4737, format="%.4f")
            else:
                it_lat, it_lon, _ = CITY_PRESETS[it_preset]

            if st.form_submit_button("Append to Schedule"):
    place_to_save = it_place.strip() if it_place.strip() else f"{it_cat} Stop"
    add_itinerary_item(it_day, it_time, place_to_save, it_cat, it_notes, it_cost, it_lat, it_lon)
    st.rerun()

# ------------------------------------------------------------------------------
# TAB 6: PACKING & EMERGENCY VAULT
# ------------------------------------------------------------------------------
with tab_vault:
    col_v1, col_v2 = st.columns([1.2, 1], gap="large")

    with col_v1:
        st.markdown("#### Travel Checklist & Gear Manifest")
        if not df_checklist.empty:
            for _, chk in df_checklist.iterrows():
                is_done = bool(chk["is_done"])
                new_state = st.checkbox(f"{chk['item']}  ·  `{chk['category']}`", value=is_done, key=f"c_item_{chk['id']}")
                if new_state != is_done:
                    toggle_checklist_item(chk["id"], new_state)
                    st.rerun()

            del_chk = st.number_input("Remove Item ID", min_value=1, step=1, key="chk_del_id")
            if st.button("Delete Checklist Entry"):
                delete_checklist_item(del_chk)
                st.rerun()

        with st.form("add_chk_form", clear_on_submit=True):
            ci_txt = st.text_input("New Item", placeholder="e.g. Physical backup ATM cards")
            ci_cat = st.selectbox("Category", ["Essentials", "Finance", "Tech", "Electronics", "Wardrobe", "Transit", "Medicine"])
            if st.form_submit_button("Add to Manifest") and ci_txt:
                add_checklist_item(ci_txt, ci_cat)
                st.rerun()

    with col_v2:
        st.markdown("#### Overseas Emergency & Embassy Vault")
        st.markdown("""
        <div class="v-card">
            <div style="font-size: 13px; font-weight: 700; color: #E2B857; margin-bottom: 6px;">
                Critical International Protocols
            </div>
            <div style="font-size: 12px; color: #94A3B8; line-height: 1.7;">
                • <b>Digital Wallet Safety:</b> Pre-link YouTrip / Revolut / Trust cards to Alipay / WeChat Pay.<br/>
                • <b>High-Speed Train Boarding:</b> Physical passports work at automated China 12306 e-gates.<br/>
                • <b>Data & Connectivity:</b> Roaming eSIMs avoid strict regional firewalls automatically.
            </div>
            <hr style="border-color: rgba(255,255,255,0.08); margin: 12px 0;"/>
            <div style="font-size: 13px; font-weight: 700; color: #E2B857; margin-bottom: 6px;">
                Diplomatic & Emergency Consulates
            </div>
            <div style="font-size: 12px; color: #94A3B8; line-height: 1.7;">
                • <b>Singapore Embassy Beijing:</b> +86-10-6532-1115<br/>
                • <b>Consulate-General Shanghai:</b> +86-21-6278-5566<br/>
                • <b>Consulate-General Tokyo:</b> +81-3-3584-6632<br/>
                • <b>High Commission Kuala Lumpur:</b> +60-3-2161-6277<br/>
                • <b>Local Emergency:</b> Police: 110 (CN) / 110 (JP) / 999 (MY)
            </div>
        </div>
        """, unsafe_allow_html=True)
