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

# --- 1. Page Configuration & SaaS Design System ---
st.set_page_config(
    page_title="Travel Companion",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Clean typography & neutral baseline */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Modern tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: transparent;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding-bottom: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 38px;
        border-radius: 6px 6px 0 0;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0 16px;
        border: none !important;
        background-color: transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #2563eb !important;
        color: #2563eb !important;
    }

    /* Minimalist status chips */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid rgba(128, 128, 128, 0.25);
    }

    /* Subtle buttons */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.88rem;
        padding: 0.4rem 1rem;
        transition: all 0.15s ease;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Setup & Persistence ---
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
            trip_day INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            estimated_cost REAL,
            location_name TEXT
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

# --- 3. Live FX, Weather & Geocoding Services ---
@st.cache_data(ttl=3600)
def fetch_live_rates(base="SGD"):
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("result") == "success":
            return data.get("rates", {}), "Connected"
    except Exception:
        pass
    fallback = {
        "CNY": 5.38, "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60, "VND": 19000.0, "AUD": 1.15
    }
    return fallback, "Offline Fallback"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name or place_name.strip() == "":
        return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_saas_prod")
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
        temp = current.get("temperature_2m", 0)
        w_code = current.get("weather_code", 0)
        
        condition = "Clear"
        if w_code in [1, 2, 3]: condition = "Partly Cloudy"
        elif w_code in [45, 48]: condition = "Foggy"
        elif w_code in [51, 61, 80]: condition = "Rain Showers"
        elif w_code >= 63: condition = "Heavy Rain"
        
        return {"temp": temp, "condition": condition, "wind": current.get("wind_speed_10m", 0)}
    except Exception:
        return None

init_db()

# --- 4. Sidebar Controls (Default: SGD -> CNY) ---
with st.sidebar:
    st.markdown("### Trip Settings")
    rates_dict, status_msg = fetch_live_rates("SGD")
    
    popular_currencies = ["CNY", "JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "AUD", "Other"]
    selected_foreign = st.selectbox("Destination Currency", popular_currencies, index=0)
    foreign_curr = st.text_input("Custom Code", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 5.38))
    rate = st.number_input(f"Rate (1 SGD = X {foreign_curr})", value=default_rate, format="%.4f")
    st.caption(f"FX Feed: **{status_msg}**")

    st.divider()
    st.markdown("### Financial Targets")
    total_budget_sgd = st.number_input("Budget (SGD)", value=3500.0, step=100.0)
    trip_days = st.number_input("Duration (Days)", min_value=1, value=7, step=1)

    st.divider()
    st.markdown("### Group Members")
    members_str = st.text_input("Names (comma-separated)", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

# --- 5. Application Header & Telemetry ---
df = get_expenses()
total_spent_sgd = df["amount_home"].sum() if not df.empty else 0.0
remaining_budget = total_budget_sgd - total_spent_sgd
pct_spent = min(100.0, (total_spent_sgd / total_budget_sgd * 100.0)) if total_budget_sgd > 0 else 0.0

col_head, col_weather = st.columns([2.2, 1.1])

with col_head:
    st.markdown("## Travel Companion")
    st.caption(f"Base: **SGD** • Active Trip: **{foreign_curr}** • Destination: **Guangzhou, China**")

with col_weather:
    # Weather for Guangzhou default
    r_lat, r_lon, active_city = 23.1291, 113.2644, "Guangzhou"
    weather = get_live_weather(r_lat, r_lon)
    if weather:
        with st.container(border=True):
            w_c1, w_c2 = st.columns([1.5, 1])
            with w_c1:
                st.markdown(f"**{active_city}** &nbsp;•&nbsp; {weather['condition']}")
                st.caption(f"Wind: {weather['wind']} km/h")
            with w_c2:
                st.markdown(f"### {weather['temp']}°C")

# --- 6. Quick Entry Bar ---
with st.expander("➕ Log an Expense", expanded=False):
    with st.form("quick_log_form", clear_on_submit=True):
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            desc = st.text_input("Description*", placeholder="e.g., Dim Sum Lunch")
            loc = st.text_input("Location / Landmark", placeholder="e.g., Tianhe District, Guangzhou")
        with col_f2:
            amt = st.number_input(f"Amount ({foreign_curr})*", min_value=0.0, step=10.0)
            category = st.selectbox("Category", ["Food & Dining", "Transport", "Activities", "Accommodation", "Shopping", "Other"])
        with col_f3:
            payer = st.selectbox("Paid By", members if members else ["Me"])
            t_day = st.number_input("Trip Day #", min_value=1, value=1, step=1)
            exp_date = st.date_input("Date", value=date.today())

        submitted = st.form_submit_button("Save Transaction", use_container_width=True)
        if submitted:
            if desc and amt > 0:
                lat, lon = geocode_place(loc)
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), loc, lat, lon, t_day)
                st.toast(f"Saved: {desc}", icon="✅")
                st.rerun()
            else:
                st.error("Please provide both a description and an amount.")

# --- 7. Main Navigation Tabs ---
tab_ledger, tab_map, tab_settle, tab_planner, tab_fx = st.tabs([
    "Overview & Ledger",
    "Route Map",
    "Settlement",
    "Planner & Packing",
    "FX & Analytics"
])

# --- TAB 1: Overview & Ledger ---
with tab_ledger:
    # High-density metrics row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Spend (SGD)", f"${total_spent_sgd:,.2f}", f"{pct_spent:.1f}% of budget")
    m2.metric("Remaining Budget", f"${remaining_budget:,.2f}", f"${(remaining_budget/trip_days if trip_days>0 else 0):,.2f}/day")
    m3.metric("Logged Entries", len(df))
    m4.metric("Active FX Rate", f"1 SGD = {rate:.2f} {foreign_curr}")

    st.progress(pct_spent / 100.0)
    st.divider()

    col_view1, col_view2 = st.columns([3, 1])
    with col_view1:
        st.markdown("#### Transaction Ledger")
    with col_view2:
        if not df.empty:
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            st.download_button("Export CSV", data=csv_buf.getvalue(), file_name=f"trip_ledger_{date.today()}.csv", mime="text/csv", use_container_width=True)

    if not df.empty:
        # Formatted table view with clean columns
        view_df = df[["trip_day", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by", "location_name"]].copy()
        view_df.columns = ["Day", "Date", "Description", "Category", "Foreign Amount", "Currency", "SGD Equivalent", "Paid By", "Location"]
        
        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "SGD Equivalent": st.column_config.NumberColumn(format="$%.2f"),
                "Foreign Amount": st.column_config.NumberColumn(format="%.2f")
            }
        )

        with st.expander("Manage Records"):
            del_id = st.selectbox("Select entry to remove", df["id"].tolist(), format_func=lambda x: f"ID #{x} — {df[df['id']==x]['description'].values[0]} (${df[df['id']==x]['amount_home'].values[0]:.2f} SGD)")
            if st.button("Delete Entry", type="secondary"):
                delete_expense(del_id)
                st.rerun()
    else:
        st.info("No expenses logged yet. Use the quick entry bar above to record your first stop.")

# --- TAB 2: Filterable Route Map ---
with tab_map:
    map_data = df.dropna(subset=["latitude", "longitude"])
    
    col_m1, col_m2 = st.columns([3, 1])
    with col_m1:
        categories = ["All Categories"] + (list(map_data["category"].unique()) if not map_data.empty else [])
        selected_cat = st.selectbox("Filter Pins by Category", categories, label_visibility="collapsed")
    with col_m2:
        draw_lines = st.checkbox("Connect Route Lines", value=True)

    filtered_map = map_data if selected_cat == "All Categories" else map_data[map_data["category"] == selected_cat]

    center_lat, center_lon, zoom = (
        (float(filtered_map["latitude"].mean()), float(filtered_map["longitude"].mean()), 12)
        if not filtered_map.empty else (23.1291, 113.2644, 11)
    )

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="CartoDB positron")

    points = []
    if not filtered_map.empty:
        for _, row in filtered_map.iterrows():
            points.append([float(row["latitude"]), float(row["longitude"])])
            popup_html = f"<b>{row['description']}</b><br>Day {row['trip_day']} • ${row['amount_home']:.2f} SGD<br>Paid by: {row['paid_by']}"
            folium.Marker(
                [float(row["latitude"]), float(row["longitude"])],
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"Day {row['trip_day']}: {row['description']}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        if draw_lines and len(points) > 1:
            folium.PolyLine(points, color="#2563eb", weight=3, opacity=0.7, dash_array="5, 10").add_to(m)

    st_folium(m, height=480, use_container_width=True)

# --- TAB 3: Settlement Engine ---
with tab_settle:
    st.markdown("#### Fair Share & Group Settlement")
    if not df.empty and members:
        fair_share = total_spent_sgd / len(members)
        paid_map = df.groupby("paid_by")["amount_home"].sum().to_dict()
        balances = {m: paid_map.get(m, 0.0) - fair_share for m in members}

        col_s1, col_s2 = st.columns([1, 1.5])
        with col_s1:
            with st.container(border=True):
                st.markdown("**Group Balances**")
                for m, bal in balances.items():
                    color = "green" if bal > 0.01 else ("red" if bal < -0.01 else "gray")
                    st.write(f"• **{m}**: Paid `${paid_map.get(m, 0.0):,.2f}` (Net: :{color}[${bal:+,.2f}])")

        with col_s2:
            with st.container(border=True):
                st.markdown("**Transfer Recommendations**")
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
                    for deb, cred, val in trans:
                        st.info(f"👉 **{deb}** transfers **${val:,.2f} SGD** to **{cred}**")
                else:
                    st.success("All accounts are balanced.")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")

# --- TAB 4: Planner & Dynamic Packing ---
with tab_planner:
    col_p1, col_p2 = st.columns([1.2, 1])

    with col_p1:
        st.markdown("#### Places to Visit / Wishlist")
        with st.form("wish_form_saas", clear_on_submit=True):
            w1, w2, w3 = st.columns([2, 1, 1])
            with w1: w_title = st.text_input("Spot Name", placeholder="e.g., Canton Tower")
            with w2: w_cost = st.number_input(f"Est. Cost ({foreign_curr})", min_value=0.0, step=10.0)
            with w3: w_cat = st.selectbox("Category", ["Activities", "Dining", "Shopping", "Transport", "Other"])
            if st.form_submit_button("Add to Wishlist", use_container_width=True) and w_title:
                add_wishlist_item(w_title, w_cat, w_cost, "Guangzhou")
                st.rerun()

        wish_df = get_wishlist()
        if not wish_df.empty:
            for _, item in wish_df.iterrows():
                with st.container(border=True):
                    c_w1, c_w2 = st.columns([3, 1])
                    with c_w1:
                        st.markdown(f"**{item['title']}** &nbsp;`{item['category']}`")
                        st.caption(f"Estimated: {item['estimated_cost']:,.0f} {foreign_curr} (~${(item['estimated_cost']/rate if rate>0 else 0):,.2f} SGD)")
                    with c_w2:
                        if st.button("Remove", key=f"del_w_{item['id']}"):
                            delete_wishlist_item(item['id'])
                            st.rerun()
        else:
            st.caption("No wishlist items added.")

    with col_p2:
        st.markdown("#### Packing Checklist")
        if "packing_list" not in st.session_state:
            st.session_state.packing_list = [
                {"id": 1, "name": "Passport & Entry Permit", "done": True},
                {"id": 2, "name": "Alipay / WeChat Pay Card Setup", "done": True},
                {"id": 3, "name": "eSIM / Roaming Data", "done": False},
                {"id": 4, "name": "Power Bank & Universal Adapter", "done": False},
                {"id": 5, "name": "Rain Jacket / Umbrella", "done": False}
            ]

        with st.form("add_pack_form", clear_on_submit=True):
            p_in1, p_in2 = st.columns([3, 1])
            with p_in1: new_pack = st.text_input("Item Name", placeholder="e.g., GaN Fast Charger", label_visibility="collapsed")
            with p_in2: p_btn = st.form_submit_button("Add", use_container_width=True)
            if p_btn and new_pack.strip():
                new_id = max([x["id"] for x in st.session_state.packing_list], default=0) + 1
                st.session_state.packing_list.append({"id": new_id, "name": new_pack.strip(), "done": False})
                st.rerun()

        total_p = len(st.session_state.packing_list)
        done_p = sum(1 for x in st.session_state.packing_list if x["done"])
        st.progress(done_p / total_p if total_p > 0 else 0)
        st.caption(f"**{done_p}/{total_p}** items ready ({int((done_p/total_p*100) if total_p>0 else 0)}%)")

        for item in list(st.session_state.packing_list):
            chk_col, del_col = st.columns([4, 1])
            with chk_col:
                checked = st.checkbox(item["name"], value=item["done"], key=f"p_id_{item['id']}")
                if checked != item["done"]:
                    item["done"] = checked
                    st.rerun()
            with del_col:
                if st.button("✖", key=f"d_p_{item['id']}"):
                    st.session_state.packing_list = [x for x in st.session_state.packing_list if x["id"] != item["id"]]
                    st.rerun()

# --- TAB 5: FX Matrix & Category Breakdown ---
with tab_fx:
    c_fx1, c_fx2 = st.columns(2)
    with c_fx1:
        st.markdown("#### Live Exchange Rates (per 1 SGD)")
        matrix_data = []
        for curr_code in ["CNY", "JPY", "MYR", "THB", "KRW", "TWD", "USD", "EUR", "GBP", "AUD"]:
            if curr_code in rates_dict:
                matrix_data.append({
                    "Currency": curr_code,
                    "Rate": f"{rates_dict[curr_code]:,.2f}",
                    "SGD 100 Equivalent": f"{(100 * rates_dict[curr_code]):,.2f} {curr_code}"
                })
        st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

    with c_fx2:
        st.markdown("#### Spending by Category")
        if not df.empty:
            cat_totals = df.groupby("category")["amount_home"].sum()
            st.bar_chart(cat_totals, color="#2563eb")
        else:
            st.caption("No data to display category distributions.")
