import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import date, datetime
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- 1. Page Configuration & Futuristic Travel UI ---
st.set_page_config(
    page_title="Travel Companion OS",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

    :root {
        --bg-glass: rgba(255, 255, 255, 0.85);
        --border-glass: rgba(226, 232, 240, 0.8);
        --text-primary: #0f172a;
        --text-secondary: #64748b;
        --accent-glow: #0284c7;
        --card-bg: #ffffff;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg-glass: rgba(15, 23, 42, 0.75);
            --border-glass: rgba(51, 65, 85, 0.7);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-glow: #38bdf8;
            --card-bg: #1e293b;
        }
    }

    [data-theme="dark"] {
        --bg-glass: rgba(15, 23, 42, 0.75);
        --border-glass: rgba(51, 65, 85, 0.7);
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --accent-glow: #38bdf8;
        --card-bg: #1e293b;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .font-brand {
        font-family: 'Space Grotesk', sans-serif !important;
    }

    /* Glassmorphism Dashboard Cards */
    .glass-card {
        background: var(--card-bg);
        border: 1px solid var(--border-glass);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        backdrop-filter: blur(12px);
        transition: transform 0.2s ease;
    }
    .glass-card:hover {
        transform: translateY(-2px);
    }

    /* Weather Widget Card */
    .weather-card {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
        border-radius: 16px;
        padding: 20px 24px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.4);
    }

    /* Timeline Day Badge */
    .timeline-badge {
        display: inline-block;
        background: var(--accent-glow);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    /* Tab Custom Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: var(--card-bg);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border-glass);
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 8px;
        font-weight: 600;
        color: var(--text-secondary);
        border: none !important;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background: var(--accent-glow) !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Layer with Extended Metadata ---
DB_FILE = "trip_expenses.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
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
            receipt_url TEXT,
            trip_day INTEGER DEFAULT 1
        )
    """)
    # Migration safety for existing databases
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(expenses)").fetchall()]
    for col, col_type in [("receipt_url", "TEXT"), ("trip_day", "INTEGER DEFAULT 1")]:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE expenses ADD COLUMN {col} {col_type}")
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
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY expense_date ASC, id ASC", conn)
    conn.close()
    return df

def delete_expense(exp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
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
    fallback = {"JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2, "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60}
    return fallback, "🟠 Fallback Offline"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name:
        return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_os_v3")
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
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        res = requests.get(url, timeout=5).json()
        current = res.get("current", {})
        temp = current.get("temperature_2m")
        w_code = current.get("weather_code", 0)
        
        # Simple weather code mapper
        condition = "☀️ Clear"
        if w_code in [1, 2, 3]: condition = "⛅ Partly Cloudy"
        elif w_code in [45, 48]: condition = "🌫️ Foggy"
        elif w_code in [51, 61, 80]: condition = "🌧️ Light Rain"
        elif w_code >= 63: condition = "⛈️ Heavy Rain / Storm"
        
        return {"temp": temp, "condition": condition, "wind": current.get("wind_speed_10m")}
    except Exception:
        return None

init_db()

# --- 4. Sidebar Controls & Budget Runway ---
with st.sidebar:
    st.markdown("<h2 class='font-brand'>🧭 Trip Control Center</h2>", unsafe_allow_html=True)
    rates_dict, status_msg = fetch_live_rates("SGD")
    st.caption(f"Rates Status: {status_msg}")

    popular_currencies = ["JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "Other"]
    selected_foreign = st.selectbox("Active Foreign Currency", popular_currencies, index=0)
    foreign_curr = st.text_input("Custom Code", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    rate = st.number_input(f"Exchange Rate (1 SGD = X {foreign_curr})", value=float(rates_dict.get(foreign_curr, 1.0)), format="%.4f")

    st.markdown("---")
    st.subheader("🎯 Trip Budget & Runway")
    total_budget_sgd = st.number_input("Total Trip Budget (SGD)", value=3000.0, step=100.0)
    trip_days = st.number_input("Trip Duration (Days)", min_value=1, value=7, step=1)
    
    st.markdown("---")
    st.subheader("👥 Travel Tribe")
    members_str = st.text_input("Group Members", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

# --- 5. Main Hero & Dynamic Weather Radar ---
df = get_expenses()
total_spent_sgd = df["amount_home"].sum() if not df.empty else 0.0

col_hero, col_weather = st.columns([2, 1])

with col_hero:
    st.markdown(f"""
    <div class="glass-card" style="border-left: 5px solid var(--accent-glow);">
        <h1 class="font-brand" style="margin: 0; font-size: 2.2rem; color: var(--text-primary);">Travel Companion OS</h1>
        <p style="color: var(--text-secondary); margin: 6px 0 0 0;">Interactive route planner, live telemetry, and group ledger.</p>
    </div>
    """, unsafe_allow_html=True)

with col_weather:
    # Get weather for the most recently logged place or default to Tokyo
    latest_with_coords = df.dropna(subset=["latitude", "longitude"]).tail(1)
    if not latest_with_coords.empty:
        w_lat = latest_with_coords["latitude"].values[0]
        w_lon = latest_with_coords["longitude"].values[0]
        w_place = latest_with_coords["location_name"].values[0]
    else:
        w_lat, w_lon, w_place = 35.6762, 139.6503, "Tokyo (Default)"

    weather = get_live_weather(w_lat, w_lon)
    if weather:
        st.markdown(f"""
        <div class="weather-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.9;">Destination Radar</div>
            <div style="font-size: 1.4rem; font-weight: 700; margin-top: 2px;">{w_place}</div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                <span style="font-size: 1.8rem; font-weight: 800;">{weather['temp']}°C</span>
                <span style="font-weight: 600; font-size: 0.95rem;">{weather['condition']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- 6. Top Navigation Tabs ---
tab_timeline, tab_map, tab_analytics, tab_log, tab_settle, tab_packing = st.tabs([
    "🗓️ Day Timeline",
    "🗺️ Interactive Route",
    "📈 Burn Rate & Analytics",
    "➕ Log Expense",
    "⚡ PayNow & Settle",
    "🎒 Packing Radar"
])

# --- TAB 1: Visual Day Timeline ---
with tab_timeline:
    st.subheader("🗓️ Trip Day-by-Day Itinerary Feed")
    if not df.empty:
        # Group by trip day or date
        days_present = sorted(df["trip_day"].unique())
        for d in days_present:
            day_df = df[df["trip_day"] == d]
            day_total = day_df["amount_home"].sum()

            st.markdown(f"<span class='timeline-badge'>DAY {d} &nbsp;•&nbsp; ${day_total:,.2f} SGD Spent</span>", unsafe_allow_html=True)
            for _, item in day_df.iterrows():
                loc_str = f"📍 {item['location_name']}" if item['location_name'] else "General"
                st.markdown(f"""
                <div class="glass-card" style="margin-left: 12px; border-left: 3px solid var(--accent-glow);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase;">{item['category']}</span>
                            <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-top: 2px;">{item['description']}</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px;">{loc_str} &nbsp;•&nbsp; Paid by <b>{item['paid_by']}</b></div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.3rem; font-weight: 800; color: var(--accent-glow);">${item['amount_home']:,.2f}</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">{item['amount_foreign']:,.0f} {item['currency']}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Your timeline is empty. Record expenses or stops to build your itinerary.")

# --- TAB 2: Map View ---
with tab_map:
    st.subheader("🗺️ Geographic Trip Route")
    map_data = df.dropna(subset=["latitude", "longitude"])
    if not map_data.empty:
        center_lat, center_lon = map_data["latitude"].mean(), map_data["longitude"].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

        points = []
        for _, row in map_data.iterrows():
            points.append([row["latitude"], row["longitude"]])
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=f"<b>{row['description']}</b><br>${row['amount_home']:.2f} SGD<br>Day {row['trip_day']}",
                tooltip=f"Day {row['trip_day']}: {row['description']}",
                icon=folium.Icon(color="blue", icon="plane", prefix="fa")
            ).add_to(m)

        if len(points) > 1:
            folium.PolyLine(points, color="#0284c7", weight=3, opacity=0.7, dash_array="5, 10").add_to(m)

        st_folium(m, width="100%", height=500)
    else:
        st.info("Include location names in your transactions to plot your journey.")

# --- TAB 3: Burn-Rate & Runway Analytics ---
with tab_analytics:
    st.subheader("📈 Budget Runway & Spend Velocity")
    remaining_budget = total_budget_sgd - total_spent_sgd
    pct_spent = min(100.0, (total_spent_sgd / total_budget_sgd * 100.0)) if total_budget_sgd > 0 else 0.0

    b1, b2, b3 = st.columns(3)
    b1.metric("Budget Remaining", f"${remaining_budget:,.2f} SGD", f"{100 - pct_spent:.1f}% left")
    b2.metric("Burned So Far", f"${total_spent_sgd:,.2f} SGD")
    daily_runway = remaining_budget / trip_days if trip_days > 0 else 0.0
    b3.metric("Safe Daily Allowance", f"${daily_runway:,.2f} SGD/day")

    st.markdown(f"**Budget Utilization: {pct_spent:.1f}%**")
    st.progress(pct_spent / 100.0)

    if not df.empty:
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("#### Spending by Category")
            cat_totals = df.groupby("category")["amount_home"].sum()
            st.bar_chart(cat_totals, color="#0284c7")
        with c_right:
            st.markdown("#### Spending Velocity by Day")
            day_totals = df.groupby("trip_day")["amount_home"].sum()
            st.line_chart(day_totals, color="#38bdf8")

# --- TAB 4: Log Expense & Form ---
with tab_log:
    st.subheader("➕ Record Activity & Scan Receipt")
    with st.form("modern_logger", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            desc = st.text_input("Activity / Item*", placeholder="e.g., Shinkansen Bullet Train Ticket")
            amt = st.number_input(f"Cost in {foreign_curr}*", min_value=0.0, step=10.0)
            category = st.selectbox("Category", ["Transport", "Food & Dining", "Activities", "Accommodation", "Shopping", "Nightlife", "Other"])
            loc = st.text_input("City / Venue Name", placeholder="e.g., Kyoto Station")
        with c2:
            t_day = st.number_input("Trip Day #", min_value=1, value=1, step=1)
            payer = st.selectbox("Paid By", members if members else ["Me"])
            exp_date = st.date_input("Date", value=date.today())
            uploaded_file = st.file_uploader("Upload Receipt / Photo (Optional)", type=["png", "jpg", "jpeg"])

        submit = st.form_submit_button("💾 Commit Transaction", use_container_width=True)
        if submit:
            if desc and amt > 0:
                lat, lon = geocode_place(loc)
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), loc, lat, lon, t_day)
                st.toast(f"Successfully recorded: {desc}", icon="🎉")
                st.rerun()
            else:
                st.error("Please provide both a description and an amount.")

    with st.expander("🗑️ Entry Removal"):
        if not df.empty:
            del_id = st.selectbox("Pick Entry ID to Delete", df["id"].tolist(), format_func=lambda x: f"ID #{x} - {df[df['id']==x]['description'].values[0]}")
            if st.button("Delete Permanently"):
                delete_expense(del_id)
                st.rerun()

# --- TAB 5: PayNow Settle Up Engine ---
with tab_settle:
    st.subheader("⚡ Group PayNow Debt Settlement")
    if not df.empty and members:
        fair_share = total_spent_sgd / len(members)
        paid_map = df.groupby("paid_by")["amount_home"].sum().to_dict()
        balances = {m: paid_map.get(m, 0.0) - fair_share for m in members}

        # Settle algorithm
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
            st.markdown("#### Required Transfers")
            for debtor, creditor, val in trans:
                st.markdown(f"""
                <div class="glass-card" style="border-left: 4px solid #10b981; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary);">👉 <b>{debtor}</b> pays <b>{creditor}</b></span>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">Direct Settlement via PayNow / Bank Transfer</div>
                    </div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #10b981;">${val:,.2f} SGD</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("🎉 All accounts are completely settled!")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")

# --- TAB 6: Weather-Aware Smart Packing Checklist ---
with tab_packing:
    st.subheader("🎒 Smart Travel Gear Checklist")
    
    packing_presets = [
        ("Passport & Travel Insurance", "Essentials"),
        ("Universal Power Adapter & Power Bank", "Electronics"),
        ("Foreign Currency & Credit Cards", "Essentials"),
        ("Umbrella / Lightweight Rain Shell", "Weather Gear"),
        ("Comfortable Walking Shoes", "Clothing"),
        ("Noise Cancelling Earbuds", "Electronics")
    ]
    
    if "packing_state" not in st.session_state:
        st.session_state.packing_state = {item[0]: False for item in packing_presets}

    done_count = sum(st.session_state.packing_state.values())
    total_items = len(packing_presets)
    st.progress(done_count / total_items)
    st.caption(f"Packed: {done_count} of {total_items} items ({done_count/total_items*100:.0f}%)")

    for item, category in packing_presets:
        checked = st.checkbox(f"{item} ({category})", value=st.session_state.packing_state.get(item, False))
        st.session_state.packing_state[item] = checked
