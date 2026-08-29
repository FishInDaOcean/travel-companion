import streamlit as st
import pandas as pd
import sqlite3
import requests
import pydeck as pdk
from datetime import date

# ==============================================================================
# 1. DATABASE SETUP & PERSISTENCE (EXACT PREVIOUS SCHEMA + LOCATION SUPPORT)
# ==============================================================================
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
            latitude REAL DEFAULT 35.6762,
            longitude REAL DEFAULT 139.6503
        )
    """)
    # Ensure latitude and longitude columns exist if upgrading existing db
    c.execute("PRAGMA table_info(expenses)")
    columns = [row[1] for row in c.fetchall()]
    if "latitude" not in columns:
        c.execute("ALTER TABLE expenses ADD COLUMN latitude REAL DEFAULT 35.6762")
    if "longitude" not in columns:
        c.execute("ALTER TABLE expenses ADD COLUMN longitude REAL DEFAULT 139.6503")
    conn.commit()
    conn.close()

def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date, lat=35.6762, lon=139.6503):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date, lat, lon))
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
        "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60,
        "VND": 19000.0, "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "Offline Mode (Fallback)"

init_db()

# ==============================================================================
# 2. PAGE CONFIGURATION & "QUIET LUXURY" DESIGN SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="Vanguard — Trip Budget & Splitter",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-color: #090A0F;
        --card-bg: rgba(18, 20, 29, 0.72);
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

    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px !important;
    }
    footer { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }

    /* Frosted Luxury Top Bar */
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
        margin-bottom: 24px;
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
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 14px;
        margin-bottom: 22px;
    }
    .metric-box {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 16px 20px;
    }
    .metric-box-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
        font-weight: 600;
    }
    .metric-box-val {
        font-size: 22px;
        font-weight: 600;
        color: var(--text-primary);
        font-family: 'JetBrains Mono', monospace;
        margin-top: 4px;
    }

    /* Glass Cards */
    .glass-panel {
        background: var(--card-bg);
        backdrop-filter: blur(16px);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 16px;
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

    /* Tabs Styling */
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
# 3. SIDEBAR: LIVE RATES, DESTINATION CURRENCY & GROUP SETUP
# ==============================================================================
rates_dict, status_msg = fetch_live_rates("SGD")

with st.sidebar:
    st.markdown("### ⚙️ Currency & Rates")
    st.caption(f"Status: **{status_msg}**")

    home_curr = "SGD"
    popular_currencies = ["JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Other"]
    selected_foreign = st.selectbox("Destination Currency", popular_currencies, index=0)

    if selected_foreign == "Other":
        foreign_curr = st.text_input("Enter Currency Code (e.g. CHF, NZD)", value="EUR").upper()
    else:
        foreign_curr = selected_foreign

    default_live_rate = float(rates_dict.get(foreign_curr, 1.0))

    rate = st.number_input(
        f"Rate (1 {home_curr} = X {foreign_curr})",
        value=default_live_rate,
        format="%.4f"
    )

    st.markdown("---")
    st.markdown("### 👥 Group Members")
    members_str = st.text_input("Names (comma-separated)", value="Me, Alex, Jordan")
    members = [m.strip() for m in members_str.split(",") if m.strip()]

    st.markdown("---")
    st.markdown("### ⚡ Quick Converter")
    calc_foreign = st.number_input(f"Amount in {foreign_curr}", value=1000.0, step=100.0)
    converted_sgd = (calc_foreign / rate) if rate > 0 else 0.0
    st.markdown(f"""
    <div style="background: rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.25); border-radius: 8px; padding: 10px 14px; text-align: center;">
        <span style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">Equivalent in SGD</span><br/>
        <span style="font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 600; color: #D4AF37;">S${converted_sgd:,.2f}</span>
    </div>
    """, unsafe_allow_html=True)

# Fetch latest expenses
df = get_expenses()
total_foreign = df["amount_foreign"].sum() if not df.empty else 0.0
total_sgd = df["amount_home"].sum() if not df.empty else 0.0

# Top Ribbon
st.markdown(f"""
<div class="luxury-ribbon">
    <div class="brand-title">
        <span style="color:#D4AF37;">✦</span> VANGUARD &nbsp;<span style="color:#475569; font-weight:400;">| &nbsp;Overseas Travel Budget & Splitter</span>
    </div>
    <div class="currency-ticker">1 SGD = {rate:.2f} {foreign_curr}</div>
</div>
""", unsafe_allow_html=True)

# Top Metrics Grid
st.markdown(f"""
<div class="metric-grid">
    <div class="metric-box">
        <div class="metric-box-label">Total Spent (Foreign)</div>
        <div class="metric-box-val">{total_foreign:,.2f} <span style="font-size: 13px; color: #64748B;">{foreign_curr}</span></div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Total Spent (SGD Base)</div>
        <div class="metric-box-val" style="color: #D4AF37;">S${total_sgd:,.2f}</div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Total Entries Logged</div>
        <div class="metric-box-val">{len(df)}</div>
    </div>
    <div class="metric-box">
        <div class="metric-box-label">Group Members</div>
        <div class="metric-box-val">{len(members)}</div>
    </div>
</div>
""", unsafe_allow_html=
