import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import date
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- 1. Page Configuration & Adaptive CSS System ---
st.set_page_config(
    page_title="Travel Companion — Curate & Split",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400&family=Inter:wght@400;500;600;700&display=swap');

    /* CSS Custom Properties for Light Theme (Default) */
    :root {
        --bg-card: #ffffff;
        --bg-subtle: #f4f1ea;
        --bg-pill: #f0f9ff;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #e8e2d4;
        --accent-blue: #0284c7;
        --accent-hover: #0369a1;
        --card-shadow: 0 2px 4px rgba(15, 23, 42, 0.04), 0 8px 16px -4px rgba(15, 23, 42, 0.06);
        --card-shadow-hover: 0 4px 8px rgba(15, 23, 42, 0.06), 0 14px 24px -6px rgba(15, 23, 42, 0.1);
        --banner-grad: linear-gradient(135deg, #0c4a6e 0%, #0284c7 60%, #38bdf8 100%);
    }

    /* CSS Custom Properties for Dark Theme */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-card: #1e293b;
            --bg-subtle: #0f172a;
            --bg-pill: #0c4a6e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --accent-blue: #38bdf8;
            --accent-hover: #0ea5e9;
            --card-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
            --card-shadow-hover: 0 6px 16px rgba(0, 0, 0, 0.4);
            --banner-grad: linear-gradient(135deg, #0f172a 0%, #075985 60%, #0284c7 100%);
        }
    }

    /* Streamlit Manual Dark Theme Override */
    [data-theme="dark"], [data-testid="stAppViewContainer"]:has(.st-emotion-cache-1wmy9hl) {
        --bg-card: #1e293b;
        --bg-subtle: #0f172a;
        --bg-pill: #0c4a6e;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: #334155;
        --accent-blue: #38bdf8;
        --accent-hover: #0ea5e9;
        --banner-grad: linear-gradient(135deg, #0f172a 0%, #075985 60%, #0284c7 100%);
    }

    /* Global Typography */
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Headings (Display Serif) */
    h1, h2, h3, .editorial-heading {
        font-family: 'Fraunces', Georgia, serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: var(--text-main) !important;
    }

    /* Hero Banner */
    .hero-container {
        background: var(--banner-grad);
        border-radius: 18px;
        padding: 32px 36px;
        color: #ffffff;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -10px rgba(2, 132, 199, 0.35);
    }
    .hero-container h1 {
        color: #ffffff !important;
        font-size: 2.1rem !important;
        margin-bottom: 6px;
    }
    .hero-container p {
        color: #e0f2fe;
        font-size: 1rem;
        max-width: 600px;
        margin: 0;
    }

    /* Cards */
    .travel-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
        color: var(--text-main);
        box-shadow: var(--card-shadow);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .travel-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--card-shadow-hover);
    }

    /* Badges & Chips */
    .metric-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--bg-pill);
        color: var(--accent-blue);
        font-weight: 600;
        font-size: 0.78rem;
        padding: 3px 10px;
        border-radius: 9999px;
        border: 1px solid var(--border-color);
    }
    
    .category-chip {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        background: var(--bg-subtle);
        color: var(--text-muted);
    }

    /* Tab Header Overhaul */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: var(--bg-subtle);
        padding: 5px;
        border-radius: 10px;
        border: 1px solid var(--border-color);
    }
    .stTabs [data-baseweb="tab"] {
        height: 38px;
        border-radius: 7px;
        font-weight: 500;
        color: var(--text-muted);
        border: none !important;
        background-color: transparent;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--bg-card) !important;
        color: var(--accent-blue) !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08) !important;
    }

    /* Pill Buttons */
    .stButton > button {
        border-radius: 9999px;
        background-color: var(--accent-blue);
        color: #ffffff;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1.4rem;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: var(--accent-hover);
        color: #ffffff;
    }

    /* Settlement Item */
    .settle-row {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-left: 4px solid var(--accent-blue);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        color: var(--text-main);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Database Operations ---
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
            longitude REAL
        )
    """)
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(expenses)").fetchall()]
    for col, col_type in [("location_name", "TEXT"), ("latitude", "REAL"), ("longitude", "REAL")]:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE expenses ADD COLUMN {col} {col_type}")
    conn.commit()
    conn.close()

def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date, loc_name, lat, lon):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date, location_name, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date, loc_name, lat, lon))
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

# --- 3. Live FX & Geocoding ---
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
        "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60,
        "VND": 19000.0, "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "🟠 Offline Fallback"

@st.cache_data(show_spinner=False)
def geocode_place(place_name):
    if not place_name or place_name.strip() == "":
        return None, None
    try:
        geolocator = Nominatim(user_agent="travel_companion_editorial_app_v2")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        loc = geocode(place_name)
        if loc:
            return loc.latitude, loc.longitude
    except Exception:
        pass
    return None, None

init_db()

# --- 4. Sidebar ---
with st.sidebar:
    st.markdown("<h3 class='editorial-heading'>Trip Settings</h3>", unsafe_allow_html=True)
    rates_dict, status_msg = fetch_live_rates("SGD")
    st.caption(f"FX Status: {status_msg}")

    popular_currencies = ["JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Other"]
    selected_foreign = st.selectbox("Destination Currency", popular_currencies, index=0)
    foreign_curr = st.text_input("Currency Code", value="EUR").upper() if selected_foreign == "Other" else selected_foreign

    default_rate = float(rates_dict.get(foreign_curr, 1.0))
    rate = st.number_input(f"Exchange Rate (1 SGD = X {foreign_curr})", value=default_rate, format="%.4f")

    st.markdown("---")
    st.markdown("<h4 class='editorial-heading'>Travelers</h4>", unsafe_allow_html=True)
    members_str = st.text_input("Names (comma-separated)", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

    st.markdown("---")
    st.markdown("<h4 class='editorial-heading'>Quick Converter</h4>", unsafe_allow_html=True)
    conv_val = st.number_input(f"Amount in {foreign_curr}", value=1000.0, step=100.0)
    converted_sgd = conv_val / rate if rate > 0 else 0.0
    
    st.markdown(f"""
    <div class="travel-card" style="text-align: center; padding: 12px; margin-top: 8px;">
        <span style="font-size: 0.8rem; color: var(--text-muted);">Equivalent SGD</span>
        <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-blue);">${converted_sgd:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

# --- 5. Hero Banner ---
st.markdown("""
<div class="hero-container">
    <h1>Travel Companion</h1>
    <p>Plan routes, track multi-currency budgets, and settle group expenses seamlessly.</p>
</div>
""", unsafe_allow_html=True)

df = get_expenses()

# --- 6. Navigation Tabs ---
tab_overview, tab_log, tab_map, tab_settle = st.tabs([
    "🧭 Overview & Feed",
    "➕ Log Expense",
    "🗺️ Interactive Route",
    "🤝 Settle Up"
])

# --- TAB 1: Overview & Feed ---
with tab_overview:
    if not df.empty:
        total_sgd = df["amount_home"].sum()
        avg_exp = total_sgd / len(df) if len(df) > 0 else 0.0

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(f"""
            <div class="travel-card">
                <span class="category-chip">Total Expenditure</span>
                <div style="font-size: 1.7rem; font-weight: 700; margin-top: 4px; color: var(--text-main);">
                    ${total_sgd:,.2f} <span style="font-size: 0.85rem; color: var(--text-muted);">SGD</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with k2:
            st.markdown(f"""
            <div class="travel-card">
                <span class="category-chip">Average Spend</span>
                <div style="font-size: 1.7rem; font-weight: 700; margin-top: 4px; color: var(--accent-blue);">
                    ${avg_exp:,.2f} <span style="font-size: 0.85rem; color: var(--text-muted);">SGD</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with k3:
            st.markdown(f"""
            <div class="travel-card">
                <span class="category-chip">Logged Entries</span>
                <div style="font-size: 1.7rem; font-weight: 700; margin-top: 4px; color: var(--text-main);">
                    {len(df)} <span style="font-size: 0.85rem; color: var(--text-muted);">Items</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<h3 class='editorial-heading' style='margin-top: 10px;'>Trip Ledger</h3>", unsafe_allow_html=True)

        for _, row in df.iterrows():
            loc_badge = f"<span class='metric-pill'>📍 {row['location_name']}</span>" if row['location_name'] else ""
            st.markdown(f"""
            <div class="travel-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span class="category-chip">{row['category']}</span>
                        <div style="font-family: 'Fraunces', serif; font-size: 1.15rem; font-weight: 600; margin: 6px 0 2px 0; color: var(--text-main);">
                            {row['description']}
                        </div>
                        <div style="color: var(--text-muted); font-size: 0.85rem;">
                            🗓️ {row['expense_date']} &nbsp;•&nbsp; Paid by <b>{row['paid_by']}</b> &nbsp; {loc_badge}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-blue);">${row['amount_home']:,.2f} SGD</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted);">{row['amount_foreign']:,.0f} {row['currency']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("🗑️ Delete an Entry"):
            del_id = st.selectbox(
                "Select entry to remove",
                df["id"].tolist(),
                format_func=lambda x: f"ID {x}: {df[df['id']==x]['description'].values[0]} (${df[df['id']==x]['amount_home'].values[0]:.2f} SGD)"
            )
            if st.button("Confirm Delete", type="primary"):
                delete_expense(del_id)
                st.rerun()
    else:
        st.info("No trip records found. Log your first expense in the 'Log Expense' tab!")

# --- TAB 2: Log Expense ---
with tab_log:
    st.markdown("<h3 class='editorial-heading'>Record a Transaction</h3>", unsafe_allow_html=True)
    with st.container():
        with st.form("adaptive_expense_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                desc = st.text_input("Item Description*", placeholder="e.g. Shibuya Izakaya Dinner")
                amt = st.number_input(f"Foreign Price ({foreign_curr})*", min_value=0.0, step=10.0)
                category = st.selectbox("Category", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Other"])
                loc = st.text_input("Location / Venue (Optional)", placeholder="e.g. Shibuya, Tokyo")

            with col_b:
                payer = st.selectbox("Paid By", members if members else ["Me"])
                exp_date = st.date_input("Date", value=date.today())
                live_calc = amt / rate if rate > 0 else 0.0
                st.markdown(f"""
                <div class="travel-card" style="margin-top: 24px; padding: 16px;">
                    <div style="font-size: 0.78rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">ESTIMATED HOME COST</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: var(--accent-blue);">${live_calc:,.2f} SGD</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Rate: 1 SGD = {rate} {foreign_curr}</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")
            submit_btn = st.form_submit_button("Save Transaction", use_container_width=True)

            if submit_btn:
                if desc and amt > 0:
                    lat, lon = geocode_place(loc)
                    log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), loc, lat, lon)
                    st.toast(f"Saved: {desc}", icon="✨")
                    st.rerun()
                else:
                    st.error("Please enter a description and valid amount.")

# --- TAB 3: Map View ---
with tab_map:
    st.markdown("<h3 class='editorial-heading'>Route & Locations</h3>", unsafe_allow_html=True)
    map_df = df.dropna(subset=["latitude", "longitude"])

    if not map_df.empty:
        center_lat = map_df["latitude"].mean()
        center_lon = map_df["longitude"].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

        for _, row in map_df.iterrows():
            html_popup = f"""
            <div style='font-family: Inter, sans-serif; font-size: 13px; line-height: 1.4;'>
                <b style='font-size: 14px; color: #0284c7;'>{row['description']}</b><br>
                <b>Category:</b> {row['category']}<br>
                <b>Amount:</b> ${row['amount_home']:.2f} SGD<br>
                <b>Paid by:</b> {row['paid_by']}
            </div>
            """
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=folium.Popup(html_popup, max_width=260),
                tooltip=f"{row['description']} (${row['amount_home']:.2f} SGD)",
                icon=folium.Icon(color="info", icon="map-marker", prefix="fa")
            ).add_to(m)

        st_folium(m, width="100%", height=480)
    else:
        st.info("Include place or city names when saving expenses to plot pins on this map.")

# --- TAB 4: Settlement ---
with tab_settle:
    st.markdown("<h3 class='editorial-heading'>Group Balances & Direct Settlement</h3>", unsafe_allow_html=True)
    if not df.empty and members:
        total_group = df["amount_home"].sum()
        fair_share = total_group / len(members)

        s1, s2 = st.columns(2)
        with s1:
            st.markdown(f"""
            <div class="travel-card">
                <span class="category-chip">Total Group Spend</span>
                <div style="font-size: 1.6rem; font-weight: 700; margin-top: 4px; color: var(--text-main);">${total_group:,.2f} SGD</div>
            </div>
            """, unsafe_allow_html=True)
        with s2:
            st.markdown(f"""
            <div class="travel-card">
                <span class="category-chip">Fair Share Each</span>
                <div style="font-size: 1.6rem; font-weight: 700; margin-top: 4px; color: var(--accent-blue);">${fair_share:,.2f} SGD</div>
            </div>
            """, unsafe_allow_html=True)

        paid_map = df.groupby("paid_by")["amount_home"].sum().to_dict()
        balances = {m: paid_map.get(m, 0.0) - fair_share for m in members}

        st.markdown("<h4 class='editorial-heading' style='margin-top: 15px;'>Member Net Standing</h4>", unsafe_allow_html=True)
        col_list = st.columns(len(members))
        for idx, (member_name, balance) in enumerate(balances.items()):
            status_color = "var(--accent-blue)" if balance > 0.01 else ("#f43f5e" if balance < -0.01 else "var(--text-muted)")
            status_label = "Gets Back" if balance > 0.01 else ("Owes" if balance < -0.01 else "Settled")
            with col_list[idx % len(col_list)]:
                st.markdown(f"""
                <div class="travel-card" style="text-align: center;">
                    <div style="font-weight: 700; font-size: 1rem; color: var(--text-main);">{member_name}</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Paid: ${paid_map.get(member_name, 0.0):,.2f}</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: {status_color}; margin-top: 6px;">
                        {balance:+,.2f} SGD
                    </div>
                    <span class="category-chip" style="margin-top: 6px;">{status_label}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<h4 class='editorial-heading' style='margin-top: 20px;'>Settlement Transactions</h4>", unsafe_allow_html=True)
        debtors = [[m, -bal] for m, bal in balances.items() if bal < -0.01]
        creditors = [[m, bal] for m, bal in balances.items() if bal > 0.01]

        transactions = []
        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            deb_name, deb_amt = debtors[i]
            cred_name, cred_amt = creditors[j]
            settled = min(deb_amt, cred_amt)

            transactions.append((deb_name, cred_name, settled))

            debtors[i][1] -= settled
            creditors[j][1] -= settled

            if debtors[i][1] <= 0.001: i += 1
            if creditors[j][1] <= 0.001: j += 1

        if transactions:
            for deb, cred, amt_val in transactions:
                st.markdown(f"""
                <div class="settle-row">
                    👉 <b>{deb}</b> sends <b>${amt_val:,.2f} SGD</b> to <b>{cred}</b>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("All accounts are completely balanced!")
    else:
        st.info("Log expenses and specify travelers to calculate splits.")
