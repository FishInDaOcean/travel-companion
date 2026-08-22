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

# --- 1. System Config & SaaS UI Styling ---
st.set_page_config(
    page_title="Travel Companion & Expense Engine",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    
    .taxi-card {
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin-top: 10px;
    }
    .taxi-zh { font-size: 2.2rem; font-weight: 800; color: #0f172a; line-height: 1.2; margin-bottom: 8px; }
    .taxi-pinyin { font-size: 1.1rem; color: #2563eb; font-weight: 600; }
    .taxi-en { font-size: 0.95rem; color: #64748b; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Layer with Migration ---
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
    # Itinerary Schedule Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS itinerary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_day INTEGER,
            time_slot TEXT,
            activity_title TEXT,
            location_name TEXT,
            estimated_cost REAL,
            notes TEXT,
            status TEXT DEFAULT 'Planned'
        )
    """)
    # Migration checks
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(expenses)").fetchall()]
    for col, ctype in [("split_between", "TEXT"), ("payment_method", "TEXT DEFAULT 'Card'")]:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE expenses ADD COLUMN {col} {ctype}")
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
    df = pd.read_sql_query("SELECT * FROM expenses ORDER BY trip_day ASC, expense_date ASC, id ASC", conn)
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

# --- 3. Live FX & Geocoding & Weather ---
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
    fallback = {"CNY": 5.38, "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2, "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60, "VND": 19000.0, "AUD": 1.15}
    return fallback, "🟠 Offline Mode"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name or place_name.strip() == "": return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_saas_v7")
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
        elif w_code in [51, 61, 80]: cond = "Light Rain"
        elif w_code >= 63: cond = "Heavy Rain"
        return {"temp": temp, "condition": cond, "humidity": curr.get("relative_humidity_2m", 0)}
    except Exception:
        return None

init_db()

# --- 4. Sidebar Controls ---
with st.sidebar:
    st.markdown("### 🧭 Trip Settings")
    active_dest = st.text_input("Destination City", value="Guangzhou, China")
    dest_lat, dest_lon = geocode_place(active_dest)
    if not dest_lat: dest_lat, dest_lon = 23.1291, 113.2644

    rates_dict, status_msg = fetch_live_rates("SGD")
    popular_currencies = ["CNY", "JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "AUD", "Other"]
    selected_foreign = st.selectbox("Foreign Currency", popular_currencies, index=0)
    foreign_curr = st.text_input("Custom Currency", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 5.38))
    rate = st.number_input(f"Rate (1 SGD = X {foreign_curr})", value=default_rate, format="%.4f")
    st.caption(f"Status: **{status_msg}**")

    st.divider()
    st.markdown("### 👥 Group Members")
    members_str = st.text_input("Travelers (comma-separated)", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

    st.divider()
    st.markdown("### 🎯 Total Budget & Days")
    total_budget_sgd = st.number_input("Total Trip Budget (SGD)", value=3500.0, step=100.0)
    trip_days = st.number_input("Trip Duration (Days)", min_value=1, value=7, step=1)

df = get_expenses()
total_spent_sgd = df["amount_home"].sum() if not df.empty else 0.0
remaining_budget = total_budget_sgd - total_spent_sgd

# --- 5. App Header & Live Weather Telemetry ---
col_head, col_weather = st.columns([2, 1.2])
with col_head:
    st.markdown("## Travel Companion")
    st.caption(f"Base: **SGD** • Active Target: **{foreign_curr}** (1 SGD = {rate:.2f} {foreign_curr}) • **{active_dest}**")

with col_weather:
    weather = get_live_weather(dest_lat, dest_lon)
    if weather:
        with st.container(border=True):
            w1, w2 = st.columns([1.5, 1])
            with w1:
                st.markdown(f"**{active_dest}** &nbsp;•&nbsp; {weather['condition']}")
                st.caption(f"Humidity: {weather['humidity']}%")
            with w2:
                st.markdown(f"### {weather['temp']}°C")

# --- 6. Quick Expense Entry with Granular Participation ---
with st.expander("➕ Log an Expense (With Granular Split)", expanded=False):
    with st.form("granular_log_form", clear_on_submit=True):
        f1, f2, f3 = st.columns([2, 1, 1])
        with f1:
            desc = st.text_input("Description*", placeholder="e.g., Dim Sum Lunch at Guangzhou Restaurant")
            loc = st.text_input("Location / Venue", placeholder=f"e.g., Tianhe District, {active_dest}")
        with f2:
            amt = st.number_input(f"Amount ({foreign_curr})*", min_value=0.0, step=10.0)
            category = st.selectbox("Category", ["Food & Dining", "Transport", "Activities", "Accommodation", "Shopping", "Nightlife", "Other"])
            pay_method = st.selectbox("Payment Method", ["YouTrip / Multi-Currency Card", "Cash (Physical)", "Credit Card", "Alipay / WeChat Pay"])
        with f3:
            payer = st.selectbox("Paid By", members if members else ["Me"])
            t_day = st.number_input("Trip Day #", min_value=1, value=1, step=1)
            exp_date = st.date_input("Date", value=date.today())

        st.markdown("**Who participated in this expense?** *(Uncheck anyone who shouldn't pay)*")
        split_checks = st.multiselect("Split Between", options=members, default=members)

        submit_btn = st.form_submit_button("💾 Save Transaction", use_container_width=True)
        if submit_btn:
            if desc and amt > 0 and split_checks:
                lat, lon = geocode_place(loc if loc else active_dest)
                log_expense(desc, amt, foreign_curr, rate, payer, split_checks, pay_method, category, str(exp_date), loc, lat, lon, t_day)
                st.toast(f"Saved: {desc} (Split among {len(split_checks)} people)", icon="✅")
                st.rerun()
            else:
                st.error("Please fill in description, amount > 0, and at least 1 person to split.")

# --- 7. Main Feature Navigation ---
tab_ledger, tab_budgets, tab_settle, tab_itinerary, tab_taxi, tab_map, tab_fx = st.tabs([
    "📊 Ledger & Cash Tracker",
    "🎯 Category Budgets",
    "🤝 Smart Settlement",
    "🗓️ Day Itinerary & Planner",
    "🚕 Taxi & Language Card",
    "🗺️ Route Map",
    "⚡ Live FX Calculator"
])

# --- TAB 1: Ledger & Payment Method Tracker ---
with tab_ledger:
    m1, m2, m3, m4 = st.columns(4)
    pct_spent = (total_spent_sgd / total_budget_sgd * 100) if total_budget_sgd > 0 else 0
    m1.metric("Total Spent", f"${total_spent_sgd:,.2f} SGD", f"{pct_spent:.1f}% used")
    m2.metric("Remaining Budget", f"${remaining_budget:,.2f} SGD", f"${(remaining_budget/trip_days if trip_days>0 else 0):,.2f}/day")
    m3.metric("Total Entries", len(df))
    cash_spent = df[df["payment_method"].str.contains("Cash", na=False)]["amount_home"].sum() if not df.empty else 0.0
    m4.metric("Physical Cash Spent", f"${cash_spent:,.2f} SGD")

    st.progress(min(1.0, pct_spent / 100.0))
    st.divider()

    if not df.empty:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1: st.markdown("#### Itemized Records")
        with col_t2:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button("📥 Export CSV", data=buf.getvalue(), file_name=f"trip_ledger_{date.today()}.csv", mime="text/csv", use_container_width=True)

        display_cols = df[["trip_day", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by", "split_between", "payment_method"]].copy()
        display_cols.columns = ["Day", "Date", "Description", "Category", "Foreign Amt", "Cur", "SGD Cost", "Payer", "Split With", "Payment Method"]
        st.dataframe(display_cols, use_container_width=True, hide_index=True)

        with st.expander("🗑️ Delete a Record"):
            del_id = st.selectbox("Select entry to remove", df["id"].tolist(), format_func=lambda x: f"ID #{x} — {df[df['id']==x]['description'].values[0]} (${df[df['id']==x]['amount_home'].values[0]:.2f} SGD)")
            if st.button("Confirm Delete"):
                delete_expense(del_id)
                st.rerun()
    else:
        st.info("No expenses logged yet.")

# --- TAB 2: Category Budgets & Caps ---
with tab_budgets:
    st.markdown("#### 🎯 Category Spending Limits & Caps")
    st.caption("Set targeted caps per category to prevent overspending on food, transport, or shopping.")

    cat_defaults = {"Food & Dining": 1200.0, "Shopping": 800.0, "Accommodation": 900.0, "Activities": 400.0, "Transport": 200.0}
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        with st.container(border=True):
            st.markdown("**Category Budget Breakdown**")
            for cat, cap in cat_defaults.items():
                spent = df[df["category"] == cat]["amount_home"].sum() if not df.empty else 0.0
                ratio = min(1.0, spent / cap) if cap > 0 else 0.0
                status_color = "red" if spent > cap else ("orange" if spent > cap*0.8 else "green")
                
                st.write(f"**{cat}**: `${spent:,.2f}` / `${cap:,.2f} SGD` (:{status_color}[{spent/cap*100:.1f}%])")
                st.progress(ratio)

    with col_b2:
        with st.container(border=True):
            st.markdown("**Spending by Payment Method**")
            if not df.empty:
                method_group = df.groupby("payment_method")["amount_home"].sum()
                st.bar_chart(method_group, color="#2563eb")
            else:
                st.caption("No data to display.")

# --- TAB 3: Smart Settlement (Granular Math) ---
with tab_settle:
    st.markdown("#### 🤝 Exact Debt Settlement Plan")
    st.caption("Calculates exact balances based on who actually participated in each individual expense.")

    if not df.empty and members:
        net_balances = {m: 0.0 for m in members}

        for _, row in df.iterrows():
            payer = row["paid_by"]
            cost = row["amount_home"]
            split_members = [m.strip() for m in str(row["split_between"]).split(",") if m.strip() in members]
            if not split_members: split_members = [payer]
            
            per_person_share = cost / len(split_members)

            if payer in net_balances:
                net_balances[payer] += cost

            for sm in split_members:
                if sm in net_balances:
                    net_balances[sm] -= per_person_share

        col_st1, col_st2 = st.columns([1, 1.5])
        with col_st1:
            with st.container(border=True):
                st.markdown("**Net Standing**")
                for m, bal in net_balances.items():
                    color = "green" if bal > 0.01 else ("red" if bal < -0.01 else "gray")
                    st.write(f"• **{m}**: :{color}[${bal:+,.2f} SGD]")

        with col_st2:
            with st.container(border=True):
                st.markdown("**Transfer Recommendations**")
                debtors = [[m, -bal] for m, bal in balances.items() if 'balances' in locals() and bal < -0.01] if 'balances' in locals() else [[m, -bal] for m, bal in net_balances.items() if bal < -0.01]
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
                        st.info(f"👉 **{deb}** pays **{cred}** `${val:,.2f} SGD`")
                else:
                    st.success("🎉 All accounts are balanced!")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")

# --- TAB 4: Day-by-Day Itinerary & Activity Planner ---
with tab_itinerary:
    st.markdown("#### 🗓️ Day-by-Day Itinerary & Activity Schedule")
    
    with st.expander("➕ Add Planned Stop / Activity", expanded=False):
        with st.form("itinerary_form", clear_on_submit=True):
            i_c1, i_c2, i_c3 = st.columns([1, 1, 2])
            with i_c1:
                plan_day = st.number_input("Trip Day #", min_value=1, value=1, step=1)
                plan_slot = st.selectbox("Time of Day", ["Morning", "Afternoon", "Evening", "Night", "All Day"])
            with i_c2:
                plan_cost = st.number_input(f"Est. Cost ({foreign_curr})", min_value=0.0, step=10.0)
                plan_loc = st.text_input("Location / Venue", placeholder="e.g., Canton Tower")
            with i_c3:
                plan_title = st.text_input("Activity / Stop Title*", placeholder="e.g., Observation Deck & Bubble Tram")
                plan_notes = st.text_input("Notes / Booking Ref", placeholder="e.g., Booked via WeChat, tickets 7:30 PM")

            if st.form_submit_button("Schedule Activity", use_container_width=True) and plan_title:
                add_itinerary_stop(plan_day, plan_slot, plan_title, plan_loc, plan_cost, plan_notes)
                st.toast(f"Scheduled: {plan_title}", icon="🗓️")
                st.rerun()

    itin_df = get_itinerary()
    if not itin_df.empty:
        for d in sorted(itin_df["trip_day"].unique()):
            st.markdown(f"##### 📍 Day {d} Schedule")
            day_stops = itin_df[itin_df["trip_day"] == d]
            for _, stop in day_stops.iterrows():
                with st.container(border=True):
                    sc1, sc2, sc3 = st.columns([3, 1.5, 0.8])
                    with sc1:
                        st.markdown(f"**{stop['time_slot']} • {stop['activity_title']}**")
                        loc_display = f"📍 {stop['location_name']}" if stop['location_name'] else "General Location"
                        notes_display = f" &nbsp;•&nbsp; 📝 {stop['notes']}" if stop['notes'] else ""
                        st.caption(f"{loc_display}{notes_display}")
                    with sc2:
                        est_sgd = (stop['estimated_cost'] / rate) if rate > 0 else 0
                        st.markdown(f"**{stop['estimated_cost']:,.0f} {foreign_curr}** (~${est_sgd:,.2f} SGD)")
                    with sc3:
                        if st.button("Delete", key=f"del_itin_{stop['id']}"):
                            delete_itinerary_stop(stop['id'])
                            st.rerun()
    else:
        st.info("No planned activities scheduled yet. Add your day-by-day stops above!")

# --- TAB 5: Taxi & Local Language Cards (China / Guangzhou) ---
with tab_taxi:
    st.markdown("#### 🚕 Taxi Card & Local Address Helper")
    st.caption("Show this screen directly to taxi drivers or locals in China when asking for directions.")

    preset_places = {
        "Custom Location": {"zh": "请带我去这个地方", "pinyin": "Qǐng dài wǒ qù zhè ge dì fāng", "en": "Please take me to this address"},
        "Canton Tower (广州塔)": {"zh": "师傅，请带我去广州塔（海珠区阅江西路222号）", "pinyin": "Shīfu, qǐng dài wǒ qù Guǎngzhōu Tǎ", "en": "Take me to Canton Tower"},
        "Guangzhou Baiyun Airport (白云机场)": {"zh": "师傅，请去广州白云国际机场", "pinyin": "Shīfu, qǐng qù Bǎiyún Guójì Jīchǎng", "en": "Take me to Baiyun International Airport"},
        "Guangzhou South Railway Station (广州南站)": {"zh": "师傅，请带我去广州南站（高铁站）", "pinyin": "Shīfu, qǐng dài wǒ qù Guǎngzhōu Nán Zhàn", "en": "Take me to Guangzhou South High-Speed Station"},
        "Beijing Road Pedestrian Street (北京路步行街)": {"zh": "师傅，去越秀区北京路步行街", "pinyin": "Shīfu, qù Běijīng Lù Bùxíngjiē", "en": "Take me to Beijing Road Pedestrian Street"}
    }

    selected_place = st.selectbox("Select Preset Destination", list(preset_places.keys()))

    if selected_place == "Custom Location":
        custom_zh = st.text_input("Destination Name / Address (in Chinese or Pinyin)", value="请带我去白天鹅宾馆 (White Swan Hotel)")
        zh_text = custom_zh
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

# --- TAB 6: Route Map ---
with tab_map:
    map_data = df.dropna(subset=["latitude", "longitude"])
    center_lat, center_lon = (float(map_data["latitude"].mean()), float(map_data["longitude"].mean())) if not map_data.empty else (dest_lat, dest_lon)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")
    if not map_data.empty:
        points = []
        for _, row in map_data.iterrows():
            points.append([float(row["latitude"]), float(row["longitude"])])
            folium.Marker(
                [float(row["latitude"]), float(row["longitude"])],
                popup=f"<b>{row['description']}</b><br>${row['amount_home']:.2f} SGD<br>Paid by {row['paid_by']}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
        if len(points) > 1:
            folium.PolyLine(points, color="#2563eb", weight=3, opacity=0.7, dash_array="5, 10").add_to(m)

    st_folium(m, height=480, use_container_width=True)

# --- TAB 7: Live FX Calculator ---
with tab_fx:
    st.markdown("#### ⚡ Real-Time FX Calculator & Rate Matrix")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        with st.container(border=True):
            st.markdown(f"**{foreign_curr} ⇄ SGD Live Calculator**")
            slider_amt = st.slider(f"Amount in {foreign_curr}", min_value=0, max_value=10000, value=1000, step=50)
            st.markdown(f"### = ${(slider_amt/rate if rate>0 else 0):,.2f} SGD")
            st.caption(f"Current exchange rate: 1 SGD = {rate:.4f} {foreign_curr}")

    with col_c2:
        with st.container(border=True):
            st.markdown("**Popular Rates Matrix (per 1 SGD)**")
            m_list = []
            for c_code in ["CNY", "JPY", "MYR", "THB", "KRW", "TWD", "USD", "EUR", "GBP", "AUD"]:
                if c_code in rates_dict:
                    m_list.append({"Currency": c_code, "Rate": f"{rates_dict[c_code]:,.2f}", "SGD 100 =": f"{(100*rates_dict[c_code]):,.2f} {c_code}"})
            st.dataframe(pd.DataFrame(m_list), use_container_width=True, hide_index=True)
