import streamlit as st
import pandas as pd
import sqlite3
import requests
import pydeck as pdk
from datetime import date, datetime, timedelta

# ==============================================================================
# 1. DATABASE SETUP & AUTOMATIC MIGRATION (CRITICAL BUG FIX)
# ==============================================================================
DB_FILE = "trip_expenses.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Expenses Table
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
            latitude REAL DEFAULT 31.2304,
            longitude REAL DEFAULT 121.4737,
            split_with TEXT DEFAULT 'ALL'
        )
    """)
    c.execute("PRAGMA table_info(expenses)")
    exp_cols = [row[1] for row in c.fetchall()]
    if "latitude" not in exp_cols:
        c.execute("ALTER TABLE expenses ADD COLUMN latitude REAL DEFAULT 31.2304")
    if "longitude" not in exp_cols:
        c.execute("ALTER TABLE expenses ADD COLUMN longitude REAL DEFAULT 121.4737")
    if "split_with" not in exp_cols:
        c.execute("ALTER TABLE expenses ADD COLUMN split_with TEXT DEFAULT 'ALL'")

    # 2. Itinerary Table & Full Column Migration
    c.execute("""
        CREATE TABLE IF NOT EXISTS itinerary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_tag TEXT,
            time_str TEXT,
            place_name TEXT,
            category TEXT,
            notes TEXT,
            cost_foreign REAL DEFAULT 0.0,
            latitude REAL DEFAULT 31.2304,
            longitude REAL DEFAULT 121.4737
        )
    """)
    c.execute("PRAGMA table_info(itinerary)")
    itin_cols = [row[1] for row in c.fetchall()]
    expected_itin_cols = {
        "day_tag": "TEXT DEFAULT 'Day 1 • General'",
        "time_str": "TEXT DEFAULT '12:00'",
        "place_name": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT 'General'",
        "notes": "TEXT DEFAULT ''",
        "cost_foreign": "REAL DEFAULT 0.0",
        "latitude": "REAL DEFAULT 31.2304",
        "longitude": "REAL DEFAULT 121.4737"
    }
    for col_name, col_def in expected_itin_cols.items():
        if col_name not in itin_cols:
            c.execute(f"ALTER TABLE itinerary ADD COLUMN {col_name} {col_def}")

    # 3. Checklist Table & Migration
    c.execute("""
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            category TEXT,
            is_done INTEGER DEFAULT 0
        )
    """)
    c.execute("PRAGMA table_info(checklist)")
    chk_cols = [row[1] for row in c.fetchall()]
    expected_chk_cols = {
        "item": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT 'General'",
        "is_done": "INTEGER DEFAULT 0"
    }
    for col_name, col_def in expected_chk_cols.items():
        if col_name not in chk_cols:
            c.execute(f"ALTER TABLE checklist ADD COLUMN {col_name} {col_def}")

    # 4. Trip Settings Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_settings (
            id INTEGER PRIMARY KEY,
            trip_title TEXT,
            start_date TEXT,
            end_date TEXT,
            budget_sgd REAL,
            members TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# Database CRUD Operations
def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date, lat, lon, split_with):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date, latitude, longitude, split_with)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date, lat, lon, split_with))
    conn.commit()
    conn.close()

def get_expenses():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY id DESC", conn)
    conn.close()
    return df

def delete_expense(exp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
    conn.commit()
    conn.close()

def get_checklist():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM checklist ORDER BY id ASC", conn)
    conn.close()
    return df

def add_checklist_item(item, category):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO checklist (item, category, is_done) VALUES (?, ?, 0)", (item, category))
    conn.commit()
    conn.close()

def toggle_checklist_item(item_id, is_done):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE checklist SET is_done = ? WHERE id = ?", (1 if is_done else 0, item_id))
    conn.commit()
    conn.close()

def delete_checklist_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM checklist WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_itinerary():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM itinerary ORDER BY id ASC", conn)
    conn.close()
    return df

def add_itinerary_item(day_tag, time_str, place_name, category, notes, cost_foreign, lat, lon):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO itinerary (day_tag, time_str, place_name, category, notes, cost_foreign, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (day_tag, time_str, place_name, category, notes, cost_foreign, lat, lon))
    conn.commit()
    conn.close()

def delete_itinerary_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM itinerary WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_trip_settings():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT trip_title, start_date, end_date, budget_sgd, members FROM trip_settings WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "title": row[0],
            "start_date": datetime.strptime(row[1], "%Y-%m-%d").date(),
            "end_date": datetime.strptime(row[2], "%Y-%m-%d").date(),
            "budget": row[3],
            "members": row[4]
        }
    return {
        "title": "China Expedition 2026",
        "start_date": date.today(),
        "end_date": date.today() + timedelta(days=7),
        "budget": 3500.0,
        "members": "Me, Alex, Jordan"
    }

def save_trip_settings(title, start_date_str, end_date_str, budget, members):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO trip_settings (id, trip_title, start_date, end_date, budget_sgd, members)
        VALUES (1, ?, ?, ?, ?, ?)
    """, (title, start_date_str, end_date_str, budget, members))
    conn.commit()
    conn.close()

# Cached Live Exchange Rate Fetcher
@st.cache_data(ttl=3600)
def fetch_live_rates(base="SGD"):
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("result") == "success":
            return data.get("rates", {}), "Live Online"
    except Exception:
        pass
    fallback = {
        "CNY": 5.40, "MYR": 3.48, "JPY": 115.0, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60,
        "VND": 19000.0, "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "Offline Mode (Fallback)"

# Initialize and migrate DB
init_db()

# Seed default checklist items if empty
if get_checklist().empty:
    add_checklist_item("Passport & China Visa / 144h Visa-Free Entry", "Essentials")
    add_checklist_item("Alipay / WeChat Pay linked to Singapore Bank Cards", "Finance")
    add_checklist_item("Universal 3-pin Adapter & 20,000mAh Power Bank", "Electronics")
    add_checklist_item("eSIM / VPN with Roaming enabled", "Tech")
    add_checklist_item("12306 High Speed Rail app verified", "Transit")

# Seed default itinerary if empty
if get_itinerary().empty:
    add_itinerary_item("Day 1 • Arrival & The Bund", "10:00", "Yu Garden & Bazaar", "Culture", "Soup dumplings & tea house", 120.0, 31.2272, 121.4921)
    add_itinerary_item("Day 1 • Arrival & The Bund", "15:00", "The Bund Waterfront", "Sightseeing", "Historic skyline stroll", 0.0, 31.2400, 121.4900)
    add_itinerary_item("Day 1 • Arrival & The Bund", "19:30", "Lujiazui Observation Deck", "Attraction", "Shanghai Tower 118th floor", 360.0, 31.2335, 121.5056)
    add_itinerary_item("Day 2 • French Concession", "11:00", "Wukang Road & Anfu Road", "Café", "Boutique coffee & brunch", 95.0, 31.2078, 121.4428)

# ==============================================================================
# 2. PAGE CONFIGURATION & "QUIET LUXURY" UI SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="Vanguard — Travel Companion",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-color: #090A0F;
        --card-bg: rgba(18, 20, 29, 0.75);
        --border-subtle: rgba(255, 255, 255, 0.08);
        --border-hover: rgba(255, 255, 255, 0.18);
        --accent-gold: #D4AF37;
        --accent-gold-glow: rgba(212, 175, 55, 0.18);
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
        --text-muted: #64748B;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: var(--bg-color) !important;
        color: var(--text-primary) !important;
    }

    header[data-testid="stHeader"] { background: transparent !important; }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px !important;
    }
    footer { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }

    /* Frosted Luxury Top Ribbon */
    .luxury-ribbon {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 24px;
        background: var(--card-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        margin-bottom: 22px;
    }
    .brand-title {
        font-size: 17px;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .currency-ticker {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 500;
        color: var(--accent-gold);
        background: rgba(212, 175, 55, 0.08);
        padding: 6px 14px;
        border-radius: 9999px;
        border: 1px solid rgba(212, 175, 55, 0.25);
    }

    /* Metric Grid */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 22px;
    }
    .metric-box {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 14px 18px;
    }
    .metric-box-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
        font-weight: 600;
    }
    .metric-box-val {
        font-size: 20px;
        font-weight: 600;
        color: var(--text-primary);
        font-family: 'JetBrains Mono', monospace;
        margin-top: 4px;
    }

    /* Glass Panels */
    .glass-panel {
        background: var(--card-bg);
        backdrop-filter: blur(16px);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 16px;
    }

    /* Luxury Timeline Node */
    .luxury-node {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 12px 16px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        margin-bottom: 8px;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .luxury-node:hover {
        background: rgba(255, 255, 255, 0.04);
        border-color: rgba(212, 175, 55, 0.35);
        transform: translateX(3px);
    }

    /* Buttons */
    div.stButton > button {
        background-color: var(--accent-gold) !important;
        color: #090A0F !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        background-color: #E5C358 !important;
        box-shadow: 0 0 18px var(--accent-gold-glow) !important;
        transform: translateY(-1px);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(18, 20, 29, 0.5);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border-subtle);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 38px;
        border-radius: 8px;
        color: var(--text-secondary);
        font-weight: 500;
        font-size: 13px;
        border: none !important;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. SIDEBAR: TRIP DURATION (AMT OF DAYS), DATES & RATES
# ==============================================================================
rates_dict, status_msg = fetch_live_rates("SGD")
current_settings = get_trip_settings()

with st.sidebar:
    st.markdown("### ✈️ Trip Dates & Duration")
    
    trip_title_input = st.text_input("Trip Title", value=current_settings["title"])
    
    c_d1, c_d2 = st.columns(2)
    start_date_val = c_d1.date_input("Start Date", value=current_settings["start_date"])
    end_date_val = c_d2.date_input("End Date", value=current_settings["end_date"])
    
    if end_date_val < start_date_val:
        end_date_val = start_date_val
        
    total_days = (end_date_val - start_date_val).days + 1
    total_nights = max(0, total_days - 1)
    
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px;">
        <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">Duration Breakdown</div>
        <div style="font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 600; color: #D4AF37; margin-top: 2px;">
            {total_days} Days / {total_nights} Nights
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚙️ Currency & Live Rates")
    st.caption(f"Status: **{status_msg}**")

    home_curr = "SGD"
    # Chinese Yuan (CNY) is explicitly FIRST
    popular_currencies = ["CNY", "MYR", "JPY", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Other"]
    selected_foreign = st.selectbox("Destination Currency", popular_currencies, index=0)

    if selected_foreign == "Other":
        foreign_curr = st.text_input("Enter Currency Code (e.g. HKD, CHF)", value="HKD").upper()
    else:
        foreign_curr = selected_foreign

    default_live_rate = float(rates_dict.get(foreign_curr, 5.40))

    rate = st.number_input(
        f"Rate (1 {home_curr} = X {foreign_curr})",
        value=default_live_rate,
        format="%.4f"
    )

    st.markdown("---")
    st.markdown("### 🎯 Trip Budget Goal")
    budget_goal = st.number_input("Allocated Budget (SGD)", min_value=0.0, value=float(current_settings["budget"]), step=250.0)
    
    daily_budget_allowance = (budget_goal / total_days) if total_days > 0 else budget_goal
    st.caption(f"Daily Allowance: **S${daily_budget_allowance:,.2f} / day**")

    st.markdown("---")
    st.markdown("### 👥 Group Members")
    members_str = st.text_input("Names (comma-separated)", value=current_settings["members"])
    members = [m.strip() for m in members_str.split(",") if m.strip()]
    if not members:
        members = ["Me"]

    # Save Settings
    if (trip_title_input != current_settings["title"] or 
        start_date_val != current_settings["start_date"] or 
        end_date_val != current_settings["end_date"] or 
        budget_goal != current_settings["budget"] or 
        members_str != current_settings["members"]):
        save_trip_settings(trip_title_input, str(start_date_val), str(end_date_val), budget_goal, members_str)

    st.markdown("---")
    st.markdown("### ⚡ Quick Converter")
    calc_foreign = st.number_input(f"Amount in {foreign_curr}", value=100.0, step=50.0)
    converted_sgd = (calc_foreign / rate) if rate > 0 else 0.0
    st.markdown(f"""
    <div style="background: rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.25); border-radius: 8px; padding: 10px 14px; text-align: center;">
        <span style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">Equivalent in SGD</span><br/>
        <span style="font-family: 'JetBrains Mono'; font-size: 17px; font-weight: 600; color: #D4AF37;">S${converted_sgd:,.2f}</span>
    </div>
    """, unsafe_allow_html=True)

# Fetch latest data
df_expenses = get_expenses()
df_checklist = get_checklist()
df_itinerary = get_itinerary()

total_foreign = df_expenses["amount_foreign"].sum() if not df_expenses.empty else 0.0
total_sgd = df_expenses["amount_home"].sum() if not df_expenses.empty else 0.0
remaining_budget = budget_goal - total_sgd
burn_pct = min(100.0, (total_sgd / budget_goal * 100.0)) if budget_goal > 0 else 0.0

# Trip Status / Countdown calculation
today = date.today()
if today < start_date_val:
    trip_status_text = f"Starts in {(start_date_val - today).days} days"
elif today > end_date_val:
    trip_status_text = "Trip Completed"
else:
    day_num = (today - start_date_val).days + 1
    trip_status_text = f"Day {day_num} of {total_days}"

# Top Ribbon
st.markdown(f"""
<div class="luxury-ribbon">
    <div class="brand-title">
        <span style="color:#D4AF37;">✦</span> {trip_title_input} &nbsp;<span style="color:#475569; font-weight:400;">| &nbsp;{total_days} Days ({start_date_val.strftime('%b %d')} – {end_date_val.strftime('%b %d')})</span>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
        <div class="currency-ticker">1 SGD ≈ {rate:.2f} {foreign_curr}</div>
        <div style="font-size: 12px; color: #94A3B8; font-family: 'JetBrains Mono'; background: rgba(255,255,255,0.05); padding: 5px 10px; border-radius: 6px;">{trip_status_text}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Overview Metrics Strip
st.markdown(f"""
<div class="metric-grid">
    <div class="metric-box">
        <div class="metric-box-label">Total Duration</div>
        <div class="metric-box-val">{total_days} <span style="font-size: 13px; color: #64748B;">Days ({total_nights}N)</span></div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Total Spent (SGD)</div>
        <div class="metric-box-val" style="color: #D4AF37;">S${total_sgd:,.2f}</div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Daily Avg Spend</div>
        <div class="metric-box-val">S${(total_sgd / total_days):,.2f} <span style="font-size: 12px; color: #64748B;">/day</span></div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Remaining Balance</div>
        <div class="metric-box-val" style="color: {'#34D399' if remaining_budget >= 0 else '#F87171'};">S${remaining_budget:,.2f}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. WORKSPACE TABS
# ==============================================================================
tab_add, tab_breakdown, tab_map, tab_split, tab_planner, tab_check = st.tabs([
    "➕ Add Expense", 
    "📊 Ledger & Daily Burn", 
    "🗺️ Spatial Map (Zero API Key)", 
    "🤝 Smart Settle & Split",
    "📅 Dynamic Itinerary",
    "✓ Packing Vault"
])

# Destination coordinate presets (China prioritized)
CITY_PRESETS = {
    "Shanghai, China (31.2304, 121.4737)": (31.2304, 121.4737),
    "Beijing, China (39.9042, 116.4074)": (39.9042, 116.4074),
    "Shenzhen, China (22.5431, 114.0579)": (22.5431, 114.0579),
    "Guangzhou, China (23.1291, 113.2644)": (23.1291, 113.2644),
    "Chengdu, China (30.5728, 104.0668)": (30.5728, 104.0668),
    "Hangzhou, China (30.2741, 120.1551)": (30.2741, 120.1551),
    "Chongqing, China (29.4316, 106.9123)": (29.4316, 106.9123),
    "Hong Kong (22.3193, 114.1694)": (22.3193, 114.1694),
    "Singapore (1.3521, 103.8198)": (1.3521, 103.8198),
    "Tokyo, Japan (35.6762, 139.6503)": (35.6762, 139.6503),
    "Seoul, South Korea (37.5665, 126.9780)": (37.5665, 126.9780),
    "Bangkok, Thailand (13.7563, 100.5018)": (13.7563, 100.5018),
    "Kuala Lumpur, Malaysia (3.1390, 101.6869)": (3.1390, 101.6869),
    "Custom Coordinates": (0.0, 0.0)
}

# ------------------------------------------------------------------------------
# TAB 1: ADD EXPENSE
# ------------------------------------------------------------------------------
with tab_add:
    st.markdown("#### Log New Expense")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        desc = st.text_input("Description", placeholder="e.g. Haidilao Hotpot, High-Speed Rail Shanghai-Hangzhou")
        amt = st.number_input(f"Amount in {foreign_curr}", min_value=0.0, value=150.0, step=10.0)
        category = st.selectbox("Category", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Entertainment", "Other"])
        
        split_type = st.radio("Split Strategy", ["Split Equally (Everyone)", "Custom Members Only"], horizontal=True)
        if split_type == "Custom Members Only":
            selected_split_members = st.multiselect("Select Included Members", members, default=members)
            split_with_str = ",".join(selected_split_members) if selected_split_members else "ALL"
        else:
            split_with_str = "ALL"

    with col2:
        payer = st.selectbox("Paid By", members)
        exp_date = st.date_input("Date", value=date.today())
        
        selected_city = st.selectbox("Map Location Preset", list(CITY_PRESETS.keys()), index=0)
        if selected_city == "Custom Coordinates":
            c_lat, c_lon = st.columns(2)
            exp_lat = c_lat.number_input("Latitude", value=31.2304, format="%.4f")
            exp_lon = c_lon.number_input("Longitude", value=121.4737, format="%.4f")
        else:
            exp_lat, exp_lon = CITY_PRESETS[selected_city]

        cost_in_sgd = amt / rate if rate > 0 else 0.0
        st.info(f"Equivalent Cost: **{cost_in_sgd:,.2f} SGD** (1 SGD = {rate} {foreign_curr})")
        
        if st.button("Save Expense to Ledger", use_container_width=True):
            if desc and amt > 0:
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), exp_lat, exp_lon, split_with_str)
                st.success(f"Logged: {desc} ({amt:,.2f} {foreign_curr} ≈ S${cost_in_sgd:,.2f})")
                st.rerun()
            else:
                st.warning("Please provide a valid description and amount.")

# ------------------------------------------------------------------------------
# TAB 2: LEDGER & DAILY BURN RATE ANALYTICS
# ------------------------------------------------------------------------------
with tab_breakdown:
    if not df_expenses.empty:
        c_ledg1, c_ledg2 = st.columns([1.4, 1], gap="large")
        
        with c_ledg1:
            st.markdown("#### Expense Ledger")
            display_df = df_expenses[["id", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by", "split_with"]].copy()
            display_df = display_df.rename(columns={
                "id": "ID",
                "expense_date": "Date",
                "description": "Item",
                "category": "Category",
                "amount_foreign": f"Amount ({foreign_curr})",
                "currency": "Curr",
                "amount_home": "SGD Equiv",
                "paid_by": "Paid By",
                "split_with": "Split For"
            })
            display_df[f"Amount ({foreign_curr})"] = display_df[f"Amount ({foreign_curr})"].apply(lambda x: f"{x:,.2f}")
            display_df["SGD Equiv"] = display_df["SGD Equiv"].apply(lambda x: f"S${x:,.2f}")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            c_exp_d, c_del_d = st.columns([1, 1])
            with c_exp_d:
                csv_data = df_expenses.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Ledger (CSV)",
                    data=csv_data,
                    file_name=f"trip_expenses_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
            with c_del_d:
                del_id = st.number_input("Delete by ID", min_value=1, step=1)
                if st.button("🗑️ Delete Selected Entry"):
                    delete_expense(del_id)
                    st.rerun()

        with c_ledg2:
            st.markdown("#### Category Distribution")
            cat_summary = df_expenses.groupby("category")["amount_home"].sum().reset_index()
            cat_summary["Percentage"] = (cat_summary["amount_home"] / total_sgd * 100).apply(lambda x: f"{x:.1f}%")
            cat_summary["Total SGD"] = cat_summary["amount_home"].apply(lambda x: f"S${x:,.2f}")
            
            st.dataframe(cat_summary[["category", "Total SGD", "Percentage"]].rename(columns={"category": "Category"}), use_container_width=True, hide_index=True)
            st.bar_chart(data=cat_summary.set_index("category")["amount_home"], color="#D4AF37")
            
            st.markdown("#### Daily Spending Trend (SGD)")
            daily_summary = df_expenses.groupby("expense_date")["amount_home"].sum().reset_index()
            st.line_chart(data=daily_summary.set_index("expense_date")["amount_home"], color="#38BDF8")
    else:
        st.info("No expenses recorded yet. Log your first expense above.")

# ------------------------------------------------------------------------------
# TAB 3: SPATIAL MAP (100% FIXED ZERO-API-KEY VECTOR MAP)
# ------------------------------------------------------------------------------
with tab_map:
    st.markdown("#### Geographic Expense & Itinerary Visualizer")
    
    map_mode = st.radio("Map Rendering Engine", ["✦ Minimalist Dark Vector (Carto - Zero Token)", "✦ Native Map"], horizontal=True)
    
    map_points = []
    if not df_expenses.empty and "latitude" in df_expenses.columns:
        for _, row in df_expenses.iterrows():
            if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                map_points.append({
                    "title": str(row["description"]),
                    "category": str(row["category"]),
                    "subtitle": f"Expense: S${row['amount_home']:.2f} (Paid by {row['paid_by']})",
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "type": "expense"
                })
                
    if not df_itinerary.empty:
        for _, row in df_itinerary.iterrows():
            if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                map_points.append({
                    "title": str(row["place_name"]),
                    "category": str(row["category"]),
                    "subtitle": f"Itinerary: {row['day_tag']} @ {row['time_str']}",
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "type": "itinerary"
                })

    df_map = pd.DataFrame(map_points)
    
    if not df_map.empty:
        all_cats = ["All Categories"] + list(df_map["category"].unique())
        sel_cat = st.segmented_control("Filter Category", all_cats, default="All Categories", label_visibility="collapsed")
        
        filtered_map = df_map if sel_cat == "All Categories" else df_map[df_map["category"] == sel_cat]
        
        if map_mode == "✦ Native Map":
            st.map(filtered_map, latitude="lat", longitude="lon", size=20, color="#D4AF37", use_container_width=True)
        else:
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=filtered_map,
                get_position="[lon, lat]",
                get_color="[212, 175, 55, 230]",
                get_radius=150,
                radius_min_pixels=7,
                radius_max_pixels=18,
                pickable=True,
                auto_highlight=True,
            )

            path_data = [{"path": filtered_map[["lon", "lat"]].values.tolist()}]
            path_layer = pdk.Layer(
                "PathLayer",
                data=path_data,
                get_path="path",
                get_color="[212, 175, 55, 120]",
                width_scale=20,
                width_min_pixels=2,
            )

            view_state = pdk.ViewState(
                latitude=filtered_map["lat"].mean(),
                longitude=filtered_map["lon"].mean(),
                zoom=11.5,
                pitch=20,
            )

            deck = pdk.Deck(
                layers=[path_layer, scatter_layer],
                initial_view_state=view_state,
                map_provider="carto",  # Explicitly prevents Mapbox token requirement
                map_style="dark",
                tooltip={
                    "html": "<b>{title}</b><br/>Category: {category}<br/>{subtitle}",
                    "style": {"backgroundColor": "#12131A", "color": "#F8FAFC", "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px"}
                }
            )
            st.pydeck_chart(deck, use_container_width=True)
    else:
        st.info("No location pins available yet.")

# ------------------------------------------------------------------------------
# TAB 4: SMART SETTLE-UP & MINIMAL P2P TRANSFERS
# ------------------------------------------------------------------------------
with tab_split:
    st.markdown("#### Smart Group Split & Optimized Debt Settlement")
    
    if not df_expenses.empty and members:
        paid_map = {m: 0.0 for m in members}
        owed_map = {m: 0.0 for m in members}
        
        for _, row in df_expenses.iterrows():
            cost = row["amount_home"]
            payer_name = row["paid_by"]
            if payer_name in paid_map:
                paid_map[payer_name] += cost
            
            split_rule = str(row["split_with"])
            if split_rule == "ALL" or not split_rule:
                participants = members
            else:
                participants = [p.strip() for p in split_rule.split(",") if p.strip() in members]
                if not participants:
                    participants = members
            
            per_person_share = cost / len(participants)
            for p in participants:
                owed_map[p] += per_person_share

        col_b1, col_b2 = st.columns([1.2, 1], gap="large")
        
        with col_b1:
            st.markdown("##### Net Position by Member")
            net_balances = []
            debtors = []
            creditors = []
            
            for m in members:
                p_paid = paid_map[m]
                p_owed = owed_map[m]
                net = p_paid - p_owed
                
                if net < -0.01:
                    debtors.append([m, abs(net)])
                elif net > 0.01:
                    creditors.append([m, net])
                    
                net_balances.append({
                    "Member": m,
                    "Total Paid (SGD)": f"${p_paid:,.2f}",
                    "Consumed Share (SGD)": f"${p_owed:,.2f}",
                    "Net Position (SGD)": f"${net:+,.2f}",
                    "Status": "✦ Gets Back" if net > 0.01 else "✦ Owes Money" if net < -0.01 else "✓ Settled"
                })
            
            st.dataframe(pd.DataFrame(net_balances), use_container_width=True, hide_index=True)

        with col_b2:
            st.markdown("##### Direct Settlement Steps (Minimum Transfers)")
            transfer_steps = []
            d_idx, c_idx = 0, 0
            
            deb_copy = [list(d) for d in debtors]
            cred_copy = [list(c) for c in creditors]
            
            while d_idx < len(deb_copy) and c_idx < len(cred_copy):
                debtor, debt_amt = deb_copy[d_idx]
                creditor, cred_amt = cred_copy[c_idx]
                
                transfer_amt = min(debt_amt, cred_amt)
                equiv_foreign = transfer_amt * rate
                transfer_steps.append(f"✦ <b>{debtor}</b> pays <b>{creditor}</b>: <span style='color:#34D399; font-family:JetBrains Mono;'>S${transfer_amt:,.2f}</span> (~{equiv_foreign:,.1f} {foreign_curr})")
                
                deb_copy[d_idx][1] -= transfer_amt
                cred_copy[c_idx][1] -= transfer_amt
                
                if deb_copy[d_idx][1] < 0.01:
                    d_idx += 1
                if cred_copy[c_idx][1] < 0.01:
                    c_idx += 1
            
            if transfer_steps:
                for step in transfer_steps:
                    st.markdown(f"""
                    <div class="glass-panel" style="padding: 14px 18px; margin-bottom: 8px;">
                        {step}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("All members are completely settled up! No transfers needed.")
    else:
        st.info("Log expenses and group members to compute settlement steps.")

# ------------------------------------------------------------------------------
# TAB 5: DYNAMIC ITINERARY SCHEDULE (DATE-AWARE)
# ------------------------------------------------------------------------------
with tab_planner:
    st.markdown("#### Dynamic Trip Schedule")
    
    generated_day_options = []
    for d_idx in range(total_days):
        current_d = start_date_val + timedelta(days=d_idx)
        generated_day_options.append(f"Day {d_idx+1} • {current_d.strftime('%a, %b %d')}")

    col_itin1, col_itin2 = st.columns([1.2, 1], gap="large")
    
    with col_itin1:
        if not df_itinerary.empty:
            existing_days = list(dict.fromkeys(df_itinerary["day_tag"].tolist()))
            combined_days = list(dict.fromkeys(generated_day_options + existing_days))
            
            selected_itin_day = st.segmented_control("Select Day", combined_days, default=combined_days[0], label_visibility="collapsed")
            
            day_items = df_itinerary[df_itinerary["day_tag"] == selected_itin_day]
            if not day_items.empty:
                for _, item in day_items.iterrows():
                    cost_sgd = item['cost_foreign'] / rate if rate > 0 else 0.0
                    cost_str = f"{item['cost_foreign']:,} {foreign_curr} (~S${cost_sgd:.1f})" if item['cost_foreign'] > 0 else "Free"
                    
                    st.markdown(f"""
                    <div class="luxury-node">
                        <div style="font-family:'JetBrains Mono'; font-size:12px; font-weight:600; color:#D4AF37; min-width:55px;">{item['time_str']}</div>
                        <div style="flex-grow:1;">
                            <div style="font-size:14px; font-weight:500;">{item['place_name']} <span style="font-size:10px; color:#64748B; border:1px solid rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; margin-left:6px;">{item['category']}</span></div>
                            <div style="font-size:12px; color:#94A3B8; margin-top:2px;">{item['notes']}</div>
                        </div>
                        <div style="font-family:'JetBrains Mono'; font-size:12px; color:#D4AF37;">{cost_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(f"No stops planned for {selected_itin_day} yet.")
                
            del_itin_id = st.number_input("Delete Stop by ID", min_value=1, step=1, key="del_itin_input")
            if st.button("Delete Selected Stop"):
                delete_itinerary_item(del_itin_id)
                st.rerun()
        else:
            st.info("No itinerary stops created yet.")

    with col_itin2:
        st.markdown("##### Add New Itinerary Stop")
        with st.form("add_itin_form", clear_on_submit=True):
            i_day = st.selectbox("Assign to Day", generated_day_options)
            c_t1, c_t2 = st.columns(2)
            i_time = c_t1.text_input("Time (HH:MM)", value="14:00")
            i_cat = c_t2.selectbox("Category", ["Sightseeing", "Dining", "Café", "Attraction", "Culture", "Transit", "Shopping"])
            i_place = st.text_input("Place / Attraction Name", placeholder="e.g. Forbidden City / Oriental Pearl")
            i_notes = st.text_input("Notes", placeholder="e.g. Book morning entry ticket")
            i_cost = st.number_input(f"Estimated Cost ({foreign_curr})", min_value=0.0, value=0.0, step=10.0)
            
            i_preset = st.selectbox("Location Preset", list(CITY_PRESETS.keys()), index=0, key="itin_city_preset")
            if i_preset == "Custom Coordinates":
                ci_lat, ci_lon = st.columns(2)
                i_lat = ci_lat.number_input("Lat", value=31.2304, format="%.4f", key="itin_lat")
                i_lon = ci_lon.number_input("Lon", value=121.4737, format="%.4f", key="itin_lon")
            else:
                i_lat, i_lon = CITY_PRESETS[i_preset]
                
            if st.form_submit_button("Add Stop to Itinerary") and i_place:
                add_itinerary_item(i_day, i_time, i_place, i_cat, i_notes, i_cost, i_lat, i_lon)
                st.rerun()

# ------------------------------------------------------------------------------
# TAB 6: PACKING & TRAVEL VAULT
# ------------------------------------------------------------------------------
with tab_check:
    c_chk1, c_chk2 = st.columns([1.2, 1], gap="large")
    
    with c_chk1:
        st.markdown("#### Travel Checklist (Persistent)")
        if not df_checklist.empty:
            for _, chk in df_checklist.iterrows():
                is_checked = bool(chk["is_done"])
                new_state = st.checkbox(f"{chk['item']}  ·  `{chk['category']}`", value=is_checked, key=f"chk_item_{chk['id']}")
                if new_state != is_checked:
                    toggle_checklist_item(chk["id"], new_state)
                    st.rerun()
                    
            del_chk_id = st.number_input("Remove Item ID", min_value=1, step=1, key="del_chk_input")
            if st.button("Delete Checklist Item"):
                delete_checklist_item(del_chk_id)
                st.rerun()

        with st.form("new_chk_form", clear_on_submit=True):
            c_txt, c_cat = st.columns([2, 1])
            new_item_val = c_txt.text_input("New Item", placeholder="e.g. Travel Insurance Policy")
            new_cat_val = c_cat.selectbox("Category", ["Essentials", "Finance", "Electronics", "Tech", "Transit", "Wardrobe", "Medicine"])
            if st.form_submit_button("Add to Checklist") and new_item_val:
                add_checklist_item(new_item_val, new_cat_val)
                st.rerun()

    with c_chk2:
        st.markdown("#### Travel Notes & Emergency Vault")
        st.markdown("""
        <div class="glass-panel">
            <div style="font-size: 13px; font-weight: 600; color: #D4AF37; margin-bottom: 6px;">Essential China Travel Apps</div>
            <div style="font-size: 12px; color: #94A3B8; line-height: 1.6;">
                • <b>Payment & Metro:</b> Alipay (TourPass / Bank Card) & WeChat Pay<br/>
                • <b>Navigation:</b> Apple Maps (Auto Gaode in China) or Amap (高德地图)<br/>
                • <b>Trains & High-Speed Rail:</b> China Railway 12306 Official App / Trip.com<br/>
                • <b>Ride-hailing:</b> Didi (integrated inside Alipay Mini Programs)
            </div>
            <hr style="border-color: rgba(255,255,255,0.06); margin: 12px 0;"/>
            <div style="font-size: 13px; font-weight: 600; color: #D4AF37; margin-bottom: 6px;">Emergency Contacts</div>
            <div style="font-size: 12px; color: #94A3B8; line-height: 1.6;">
                • Singapore Embassy Beijing: +86-10-6532-1115<br/>
                • Consulate-General in Shanghai: +86-21-6278-5566<br/>
                • Police: 110 · Ambulance: 120 · Fire: 119
            </div>
        </div>
        """, unsafe_allow_html=True)
