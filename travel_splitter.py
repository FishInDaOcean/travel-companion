import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
from datetime import date
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import io

# --- 1. System Config & Responsive CSS ---
st.set_page_config(
    page_title="Travel Companion",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }

    .stButton > button {
        min-height: 44px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.95rem;
        width: 100%;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 6px;
        scrollbar-width: none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 14px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .badge-chip {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        background: rgba(37, 99, 235, 0.1);
        color: #2563eb;
        border: 1px solid rgba(37, 99, 235, 0.2);
    }
    .method-chip {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        background: rgba(100, 116, 139, 0.1);
        color: #64748b;
    }

    .taxi-card {
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 14px;
        padding: 20px 16px;
        text-align: center;
        margin: 10px 0;
    }
    .taxi-zh { font-size: 1.8rem; font-weight: 800; color: #0f172a; line-height: 1.25; margin-bottom: 6px; }
    .taxi-pinyin { font-size: 1rem; color: #2563eb; font-weight: 600; }
    .taxi-en { font-size: 0.85rem; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Schema (Absolute Path & Persistent Settings) ---
# Guarantees the DB stays in the script's exact folder
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trip_expenses.db")

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
            split_between TEXT,
            payment_method TEXT DEFAULT 'Card',
            category TEXT,
            expense_date TEXT,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            trip_day INTEGER DEFAULT 1
        )
    """)
    
    # Automatic column patcher (ensures older DBs never crash on insert)
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(expenses)").fetchall()]
    needed_cols = [
        ("split_between", "TEXT"),
        ("payment_method", "TEXT DEFAULT 'Card'"),
        ("location_name", "TEXT"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("trip_day", "INTEGER DEFAULT 1")
    ]
    for col, ctype in needed_cols:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE expenses ADD COLUMN {col} {ctype}")

    # 2. Itinerary Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS itinerary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_day INTEGER,
            time_slot TEXT,
            activity_title TEXT,
            location_name TEXT,
            estimated_cost REAL,
            notes TEXT
        )
    """)

    # 3. Persistent App Settings (Saves destination, currency, budget across refresh)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # 4. Persistent Packing Checklist
    c.execute("""
        CREATE TABLE IF NOT EXISTS packing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            done INTEGER DEFAULT 0,
            category TEXT DEFAULT 'Essentials'
        )
    """)
    if c.execute("SELECT COUNT(*) FROM packing").fetchone()[0] == 0:
        default_items = [
            ("Passport & Chinese Visa / Entry Card", 1, "Essentials"),
            ("Alipay / WeChat Pay Linked Card", 1, "Money"),
            ("eSIM / Roaming Data", 0, "Electronics"),
            ("Power Bank & Universal GaN Adapter", 0, "Electronics"),
            ("Compact Umbrella / Rain Shell", 0, "Weather")
        ]
        c.executemany("INSERT INTO packing (name, done, category) VALUES (?, ?, ?)", default_items)

    conn.commit()
    conn.close()

# Database Helper Functions
def get_setting(key, default):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def log_expense(desc, amt_foreign, curr, rate, paid_by, split_list, pay_method, category, exp_date, loc_name, lat, lon, trip_day):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    split_str = ",".join(split_list) if split_list else paid_by
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, split_between, payment_method, category, expense_date, location_name, latitude, longitude, trip_day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, split_str, pay_method, category, exp_date, loc_name, lat, lon, trip_day))
    conn.commit()
    conn.close()

def get_expenses():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC", conn)
    conn.close()
    return df

def delete_expense(exp_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (exp_id,))
    conn.commit()
    conn.close()

def add_itinerary_stop(day, slot, title, loc, cost, notes):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO itinerary (trip_day, time_slot, activity_title, location_name, estimated_cost, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (day, slot, title, loc, cost, notes))
    conn.commit()
    conn.close()

def get_itinerary():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM itinerary ORDER BY trip_day ASC, id ASC", conn)
    conn.close()
    return df

def delete_itinerary_stop(stop_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM itinerary WHERE id = ?", (stop_id,))
    conn.commit()
    conn.close()

def get_packing_items():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM packing ORDER BY id ASC", conn)
    conn.close()
    return df

def toggle_packing_item(item_id, done_status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE packing SET done = ? WHERE id = ?", (1 if done_status else 0, item_id))
    conn.commit()
    conn.close()

def add_packing_item(name, cat):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO packing (name, done, category) VALUES (?, 0, ?)", (name, cat))
    conn.commit()
    conn.close()

def delete_packing_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM packing WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# --- 3. Live FX, Geocoding & Weather ---
@st.cache_data(ttl=3600)
def fetch_live_rates(base="SGD"):
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("result") == "success":
            return data.get("rates", {}), "🟢 Online"
    except Exception:
        pass
    fallback = {"CNY": 5.38, "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2, "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60, "VND": 19000.0, "AUD": 1.15}
    return fallback, "🟠 Offline"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name or place_name.strip() == "": return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_persistent_app")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        loc = geocode(place_name)
        if loc: return loc.latitude, loc.longitude
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=1800, show_spinner=False)
def get_live_weather(lat, lon):
    if not lat or not lon: return None
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        res = requests.get(url, timeout=5).json()
        curr = res.get("current", {})
        temp = curr.get("temperature_2m", 0)
        w_code = curr.get("weather_code", 0)
        cond = "Clear"
        if w_code in [1, 2, 3]: cond = "Partly Cloudy"
        elif w_code in [45, 48]: cond = "Foggy"
        elif w_code in [51, 61, 80]: cond = "Rain"
        elif w_code >= 63: cond = "Heavy Rain"
        return {"temp": temp, "condition": cond, "humidity": curr.get("relative_humidity_2m", 0)}
    except Exception:
        return None

init_db()

# --- 4. Sidebar Controls (Saved Permanently to SQLite) ---
with st.sidebar:
    st.markdown("### ⚙️ Trip Setup")
    
    # Load and save destination
    saved_dest = get_setting("dest", "Guangzhou, China")
    active_dest = st.text_input("Active City", value=saved_dest)
    if active_dest != saved_dest:
        set_setting("dest", active_dest)

    dest_lat, dest_lon = geocode_place(active_dest)
    if not dest_lat: dest_lat, dest_lon = 23.1291, 113.2644

    rates_dict, status_msg = fetch_live_rates("SGD")
    popular_currencies = ["CNY", "JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "AUD", "Other"]
    
    saved_curr = get_setting("currency", "CNY")
    curr_idx = popular_currencies.index(saved_curr) if saved_curr in popular_currencies else 0
    selected_foreign = st.selectbox("Currency", popular_currencies, index=curr_idx)
    
    if selected_foreign != saved_curr and selected_foreign != "Other":
        set_setting("currency", selected_foreign)

    foreign_curr = st.text_input("Custom Code", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 5.38))
    rate = st.number_input(f"1 SGD = X {foreign_curr}", value=default_rate, format="%.4f")
    st.caption(f"FX Status: **{status_msg}**")

    st.divider()
    st.markdown("### 👥 Group & Budget")
    
    saved_members = get_setting("members", "Me, Alex, Jordan")
    members_str = st.text_input("Group Members", value=saved_members)
    if members_str != saved_members:
        set_setting("members", members_str)
    members = [m.strip() for m in members_str.split(",") if m.strip()]

    saved_budget = float(get_setting("budget", 3500.0))
    total_budget_sgd = st.number_input("Budget (SGD)", value=saved_budget, step=100.0)
    if total_budget_sgd != saved_budget:
        set_setting("budget", total_budget_sgd)

    saved_days = int(get_setting("days", 7))
    trip_days = st.number_input("Days", min_value=1, value=saved_days, step=1)
    if trip_days != saved_days:
        set_setting("days", trip_days)

df = get_expenses()
total_spent_sgd = df["amount_home"].sum() if not df.empty else 0.0
remaining_budget = total_budget_sgd - total_spent_sgd

# --- 5. Header & Telemetry ---
weather = get_live_weather(dest_lat, dest_lon)
w_str = f" • {weather['temp']}°C {weather['condition']}" if weather else ""

st.markdown(f"### ✈️ Travel Companion")
st.caption(f"📍 **{active_dest}**{w_str} • **1 SGD = {rate:.2f} {foreign_curr}**")

m1, m2 = st.columns(2)
pct_spent = (total_spent_sgd / total_budget_sgd * 100) if total_budget_sgd > 0 else 0
m1.metric("Spent", f"${total_spent_sgd:,.2f}", f"{pct_spent:.0f}% of budget")
daily_allow = remaining_budget / trip_days if trip_days > 0 else 0
m2.metric("Left", f"${remaining_budget:,.2f}", f"${daily_allow:,.0f}/day")
st.progress(min(1.0, pct_spent / 100.0))

# --- 6. Quick Action Add Bar ---
with st.expander("➕ **Log New Expense**", expanded=False):
    with st.form("mobile_log_form", clear_on_submit=True):
        desc = st.text_input("Item Description*", placeholder="e.g., Dim Sum Lunch")
        
        c_amt, c_cat = st.columns([1, 1])
        with c_amt: amt = st.number_input(f"Amount ({foreign_curr})*", min_value=0.0, step=10.0)
        with c_cat: category = st.selectbox("Category", ["Food & Dining", "Transport", "Activities", "Accommodation", "Shopping", "Other"])
        
        c_pay, c_meth = st.columns([1, 1])
        with c_pay: payer = st.selectbox("Paid By", members if members else ["Me"])
        with c_meth: pay_method = st.selectbox("Method", ["YouTrip/Card", "Cash", "Alipay/WeChat", "Credit Card"])
        
        c_day, c_date = st.columns([1, 1])
        with c_day: t_day = st.number_input("Day #", min_value=1, value=1, step=1)
        with c_date: exp_date = st.date_input("Date", value=date.today())
        
        loc = st.text_input("Location / Venue (Optional)", placeholder="e.g., Tianhe District")
        split_checks = st.multiselect("Split Between", options=members, default=members)

        if st.form_submit_button("Save Transaction", use_container_width=True):
            if desc and amt > 0 and split_checks:
                lat, lon = geocode_place(loc if loc else active_dest)
                log_expense(desc, amt, foreign_curr, rate, payer, split_checks, pay_method, category, str(exp_date), loc, lat, lon, t_day)
                st.toast(f"Saved: {desc}", icon="✅")
                st.rerun()
            else:
                st.error("Please fill in description, amount, and at least 1 person.")

# --- 7. Navigation Tabs ---
tab_cards, tab_budgets, tab_settle, tab_itinerary, tab_packing, tab_taxi, tab_map, tab_fx = st.tabs([
    "💳 Ledger",
    "🎯 Budgets",
    "🤝 Split",
    "🗓️ Planner",
    "🎒 Packing",
    "🚕 Taxi",
    "🗺️ Map",
    "⚡ FX"
])

# --- TAB 1: Mobile Card Feed ---
with tab_cards:
    if not df.empty:
        c_head, c_exp = st.columns([2, 1])
        with c_head: st.markdown(f"**Activity Feed ({len(df)})**")
        with c_exp:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button("📥 CSV", data=buf.getvalue(), file_name=f"trip_{date.today()}.csv", mime="text/csv", use_container_width=True)

        for _, row in df.iterrows():
            with st.container(border=True):
                col_title, col_cost = st.columns([2.5, 1.5])
                with col_title:
                    st.markdown(f"**{row['description']}**")
                with col_cost:
                    st.markdown(f"<div style='text-align:right; font-weight:800; font-size:1.05rem; color:#2563eb;'>${row['amount_home']:,.2f} <span style='font-size:0.75rem; color:#64748b;'>SGD</span></div>", unsafe_allow_html=True)

                st.markdown(f"""
                <span class='badge-chip'>{row['category']}</span> 
                <span class='method-chip'>{row['payment_method']}</span>
                <span style='font-size:0.8rem; color:#64748b; float:right;'>{row['amount_foreign']:,.0f} {row['currency']}</span>
                """, unsafe_allow_html=True)

                loc_txt = f" • 📍 {row['location_name']}" if row['location_name'] else ""
                split_txt = "All" if len(str(row['split_between']).split(',')) == len(members) else row['split_between']
                st.caption(f"Day {row['trip_day']} ({row['expense_date']}){loc_txt}\n\nPaid by **{row['paid_by']}** • Split: *{split_txt}*")

        with st.expander("🗑️ Delete an Entry"):
            del_id = st.selectbox("Select Entry", df["id"].tolist(), format_func=lambda x: f"ID #{x}: {df[df['id']==x]['description'].values[0]} (${df[df['id']==x]['amount_home'].values[0]:.2f} SGD)")
            if st.button("Confirm Delete", type="primary", use_container_width=True):
                delete_expense(del_id)
                st.rerun()
    else:
        st.info("No expenses logged yet. Tap '+ Log New Expense' to get started.")

# --- TAB 2: Category Budgets ---
with tab_budgets:
    st.markdown("#### Category Budget Caps")
    cat_defaults = {"Food & Dining": 1200.0, "Shopping": 800.0, "Accommodation": 900.0, "Activities": 400.0, "Transport": 200.0}
    
    for cat, cap in cat_defaults.items():
        spent = df[df["category"] == cat]["amount_home"].sum() if not df.empty else 0.0
        ratio = min(1.0, spent / cap) if cap > 0 else 0.0
        status_color = "red" if spent > cap else ("orange" if spent > cap*0.8 else "green")
        
        with st.container(border=True):
            st.markdown(f"**{cat}** &nbsp;•&nbsp; :{status_color}[${spent:,.2f} / ${cap:,.2f} SGD]")
            st.progress(ratio)

    st.markdown("#### Payment Method Spend")
    if not df.empty:
        method_group = df.groupby("payment_method")["amount_home"].sum()
        st.bar_chart(method_group, color="#2563eb")

# --- TAB 3: Mobile Pairwise Settlement ---
with tab_settle:
    st.markdown("#### Group Settle Up")
    if not df.empty and members:
        net_balances = {m: 0.0 for m in members}

        for _, row in df.iterrows():
            payer = row["paid_by"]
            cost = row["amount_home"]
            split_members = [m.strip() for m in str(row["split_between"]).split(",") if m.strip() in members]
            if not split_members: split_members = [payer]
            
            per_person_share = cost / len(split_members)
            if payer in net_balances: net_balances[payer] += cost
            for sm in split_members:
                if sm in net_balances: net_balances[sm] -= per_person_share

        with st.container(border=True):
            st.markdown("**Individual Balances**")
            for m, bal in net_balances.items():
                color = "green" if bal > 0.01 else ("red" if bal < -0.01 else "gray")
                st.write(f"• **{m}**: :{color}[${bal:+,.2f} SGD]")

        st.markdown("**Transfer Recommendations**")
        debtors = [[m, -bal] for m, bal in net_balances.items() if bal < -0.01]
        creditors = [[m, bal] for m, bal in net_balances.items() if bal > 0.01]

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
            for deb, cred, val in trans:
                with st.container(border=True):
                    st.markdown(f"👉 **{deb}** sends **{cred}**")
                    st.markdown(f"<div style='font-size:1.3rem; font-weight:800; color:#10b981;'>${val:,.2f} SGD</div>", unsafe_allow_html=True)
        else:
            st.success("🎉 All accounts are balanced!")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")

# --- TAB 4: Itinerary Planner Cards ---
with tab_itinerary:
    st.markdown("#### Day Schedule")
    with st.expander("➕ Add Itinerary Activity"):
        with st.form("itin_form_mob", clear_on_submit=True):
            plan_day = st.number_input("Day #", min_value=1, value=1, step=1)
            plan_slot = st.selectbox("Slot", ["Morning", "Afternoon", "Evening", "Night", "All Day"])
            plan_title = st.text_input("Activity*", placeholder="e.g., Canton Tower Observation Deck")
            plan_cost = st.number_input(f"Cost ({foreign_curr})", min_value=0.0, step=10.0)
            plan_loc = st.text_input("Venue", placeholder="e.g., Haizhu District")
            plan_notes = st.text_input("Notes", placeholder="e.g., Tickets booked at 7:30 PM")
            
            if st.form_submit_button("Add to Schedule", use_container_width=True) and plan_title:
                add_itinerary_stop(plan_day, plan_slot, plan_title, plan_loc, plan_cost, plan_notes)
                st.rerun()

    itin_df = get_itinerary()
    if not itin_df.empty:
        for d in sorted(itin_df["trip_day"].unique()):
            st.markdown(f"**📍 Day {d}**")
            for _, stop in itin_df[itin_df["trip_day"] == d].iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{stop['time_slot']} • {stop['activity_title']}**")
                        loc_txt = f"📍 {stop['location_name']}" if stop['location_name'] else ""
                        notes_txt = f" • 📝 {stop['notes']}" if stop['notes'] else ""
                        st.caption(f"{loc_txt}{notes_txt}")
                    with c2:
                        est_sgd = (stop['estimated_cost'] / rate) if rate > 0 else 0
                        st.markdown(f"<div style='text-align:right; font-weight:700;'>${est_sgd:,.0f} SGD</div>", unsafe_allow_html=True)
                        if st.button("✖", key=f"d_it_{stop['id']}", use_container_width=True):
                            delete_itinerary_stop(stop['id'])
                            st.rerun()
    else:
        st.info("No planned stops yet.")

# --- TAB 5: Persistent Packing Checklist ---
with tab_packing:
    st.markdown("#### 🎒 Packing Checklist")
    
    with st.form("add_packing_item_form", clear_on_submit=True):
        p_c1, p_c2 = st.columns([3, 1])
        with p_c1: p_name = st.text_input("New Gear Item", placeholder="e.g., Power Bank 20000mAh", label_visibility="collapsed")
        with p_c2: p_btn = st.form_submit_button("Add", use_container_width=True)
        if p_btn and p_name.strip():
            add_packing_item(p_name.strip(), "General")
            st.rerun()

    pack_df = get_packing_items()
    if not pack_df.empty:
        total_p = len(pack_df)
        done_p = int(pack_df["done"].sum())
        st.progress(done_p / total_p if total_p > 0 else 0)
        st.caption(f"**{done_p}/{total_p}** packed ({int(done_p/total_p*100)}%)")

        for _, item in pack_df.iterrows():
            with st.container(border=True):
                chk_col, del_col = st.columns([4, 1])
                with chk_col:
                    is_done = bool(item["done"])
                    checked = st.checkbox(item["name"], value=is_done, key=f"p_item_{item['id']}")
                    if checked != is_done:
                        toggle_packing_item(item["id"], checked)
                        st.rerun()
                with del_col:
                    if st.button("✖", key=f"d_pack_{item['id']}", use_container_width=True):
                        delete_packing_item(item["id"])
                        st.rerun()
    else:
        st.info("No packing items yet.")

# --- TAB 6: Taxi Card Helper ---
with tab_taxi:
    st.markdown("#### 🚕 Taxi & Directions Card")
    preset_places = {
        "Custom Location": {"zh": "请带我去这个地方", "pinyin": "Qǐng dài wǒ qù zhè ge dì fāng", "en": "Please take me to this address"},
        "Canton Tower (广州塔)": {"zh": "师傅，请带我去广州塔（海珠区阅江西路222号）", "pinyin": "Shīfu, qǐng dài wǒ qù Guǎngzhōu Tǎ", "en": "Take me to Canton Tower"},
        "Guangzhou Baiyun Airport (白云机场)": {"zh": "师傅，请去广州白云国际机场", "pinyin": "Shīfu, qǐng qù Bǎiyún Guójì Jīchǎng", "en": "Take me to Baiyun International Airport"},
        "Guangzhou South Station (广州南站)": {"zh": "师傅，请带我去广州南站（高铁站）", "pinyin": "Shīfu, qǐng dài wǒ qù Guǎngzhōu Nán Zhàn", "en": "Take me to Guangzhou South Station"},
        "Beijing Road (北京路步行街)": {"zh": "师傅，去越秀区北京路步行街", "pinyin": "Shīfu, qù Běijīng Lù Bùxíngjiē", "en": "Take me to Beijing Road Pedestrian Street"}
    }

    selected_place = st.selectbox("Destination", list(preset_places.keys()), label_visibility="collapsed")
    if selected_place == "Custom Location":
        zh_text = st.text_input("Custom Chinese Address", value="请带我去白天鹅宾馆")
        pinyin_text = "Qǐng dài wǒ qù zhè lǐ"
        en_text = "Take me to this custom destination"
    else:
        zh_text = preset_places[selected_place]["zh"]
        pinyin_text = preset_places[selected_place]["pinyin"]
        en_text = preset_places[selected_place]["en"]

    st.markdown(f"""
    <div class="taxi-card">
        <div class="taxi-zh">{zh_text}</div>
        <div class="taxi-pinyin">{pinyin_text}</div>
        <div class="taxi-en">English: {en_text}</div>
    </div>
    """, unsafe_allow_html=True)

# --- TAB 7: Touch-Friendly Route Map ---
with tab_map:
    st.markdown("#### Trip Route Map")
    map_data = df.dropna(subset=["latitude", "longitude"])
    center_lat, center_lon = (float(map_data["latitude"].mean()), float(map_data["longitude"].mean())) if not map_data.empty else (dest_lat, dest_lon)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")
    if not map_data.empty:
        points = []
        for _, row in map_data.iterrows():
            points.append([float(row["latitude"]), float(row["longitude"])])
            folium.Marker(
                [float(row["latitude"]), float(row["longitude"])],
                popup=f"<b>{row['description']}</b><br>${row['amount_home']:.2f} SGD",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
        if len(points) > 1:
            folium.PolyLine(points, color="#2563eb", weight=3, opacity=0.7, dash_array="5, 10").add_to(m)

    st_folium(m, height=320, use_container_width=True)

# --- TAB 8: FX Calculator ---
with tab_fx:
    st.markdown(f"#### ⚡ FX Quick Calc ({foreign_curr} ⇄ SGD)")
    calc_in = st.number_input(f"Amount in {foreign_curr}", value=100.0, step=50.0)
    st.markdown(f"<div style='font-size:1.6rem; font-weight:800; color:#2563eb;'>≈ ${(calc_in/rate if rate>0 else 0):,.2f} SGD</div>", unsafe_allow_html=True)
    st.caption(f"Current Rate: 1 SGD = {rate:.4f} {foreign_curr}")

    st.divider()
    st.markdown("**Popular Rates (per 1 SGD)**")
    m_list = []
    for c_code in ["CNY", "JPY", "MYR", "THB", "KRW", "TWD", "USD", "EUR", "GBP", "AUD"]:
        if c_code in rates_dict:
            m_list.append({"Currency": c_code, "Rate": f"{rates_dict[c_code]:,.2f}", "SGD 100": f"{(100*rates_dict[c_code]):,.2f}"})
    
    st.dataframe(pd.DataFrame(m_list), use_container_width=True, hide_index=True)
