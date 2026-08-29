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
""", unsafe_allow_html=True)

# ==============================================================================
# 4. MAIN INTERFACE TABS (ALL ORIGINAL TABS + ZERO-API-KEY VECTOR MAP)
# ==============================================================================
tab_add, tab_breakdown, tab_map, tab_split = st.tabs([
    "➕ Add Expense", 
    "📊 Trip Breakdown", 
    "🗺️ Spatial Map (No API Key)", 
    "🤝 Settle Up & Bill Split"
])

# ------------------------------------------------------------------------------
# TAB 1: ADD EXPENSE (WITH OPTIONAL LOCATION COORDINATES)
# ------------------------------------------------------------------------------
with tab_add:
    st.markdown("#### Record New Expense")
    
    col1, col2 = st.columns(2, gap="large")
    with col1:
        desc = st.text_input("Description", placeholder="e.g. Ichiran Ramen, Tokyo Metro Pass")
        amt = st.number_input(f"Amount in {foreign_curr}", min_value=0.0, step=10.0)
        category = st.selectbox("Category", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Other"])
    
    with col2:
        payer = st.selectbox("Paid By", members if members else ["Me"])
        exp_date = st.date_input("Date", value=date.today())
        
        # City coordinate presets to make map pinning effortless
        preset_city = st.selectbox("Location Preset for Map", [
            "Tokyo, Japan (35.6762, 139.6503)",
            "Singapore (1.3521, 103.8198)",
            "Kuala Lumpur, Malaysia (3.1390, 101.6869)",
            "Bangkok, Thailand (13.7563, 100.5018)",
            "Seoul, South Korea (37.5665, 126.9780)",
            "Taipei, Taiwan (25.0330, 121.5654)",
            "London, UK (51.5074, -0.1278)",
            "Paris, France (48.8566, 2.3522)",
            "New York, USA (40.7128, -74.0060)",
            "Custom Coordinates"
        ])
        
        coords_map = {
            "Tokyo, Japan (35.6762, 139.6503)": (35.6762, 139.6503),
            "Singapore (1.3521, 103.8198)": (1.3521, 103.8198),
            "Kuala Lumpur, Malaysia (3.1390, 101.6869)": (3.1390, 101.6869),
            "Bangkok, Thailand (13.7563, 100.5018)": (13.7563, 100.5018),
            "Seoul, South Korea (37.5665, 126.9780)": (37.5665, 126.9780),
            "Taipei, Taiwan (25.0330, 121.5654)": (25.0330, 121.5654),
            "London, UK (51.5074, -0.1278)": (51.5074, -0.1278),
            "Paris, France (48.8566, 2.3522)": (48.8566, 2.3522),
            "New York, USA (40.7128, -74.0060)": (40.7128, -74.0060),
        }
        
        if preset_city == "Custom Coordinates":
            c_lat, c_lon = st.columns(2)
            exp_lat = c_lat.number_input("Latitude", value=35.6762, format="%.4f")
            exp_lon = c_lon.number_input("Longitude", value=139.6503, format="%.4f")
        else:
            exp_lat, exp_lon = coords_map[preset_city]

        cost_in_sgd = amt / rate if rate > 0 else 0.0
        st.info(f"Equivalent Cost: **{cost_in_sgd:,.2f} SGD** (at 1 SGD = {rate} {foreign_curr})")
        
        if st.button("Save Expense", use_container_width=True):
            if desc and amt > 0:
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date), exp_lat, exp_lon)
                st.success(f"Logged: {desc} ({amt:,.0f} {foreign_curr} ≈ {cost_in_sgd:,.2f} SGD)")
                st.rerun()
            else:
                st.warning("Please provide a valid description and amount.")

# ------------------------------------------------------------------------------
# TAB 2: TRIP BREAKDOWN & HISTORY
# ------------------------------------------------------------------------------
with tab_breakdown:
    if not df.empty:
        st.markdown("#### Expense Ledger")
        
        display_df = df[["id", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by"]].copy()
        display_df = display_df.rename(columns={
            "id": "ID",
            "expense_date": "Date",
            "description": "Description",
            "category": "Category",
            "amount_foreign": f"Amount ({foreign_curr})",
            "currency": "Currency",
            "amount_home": "Amount (SGD)",
            "paid_by": "Paid By"
        })
        
        # Format currency columns for clean readability
        display_df[f"Amount ({foreign_curr})"] = display_df[f"Amount ({foreign_curr})"].apply(lambda x: f"{x:,.2f}")
        display_df["Amount (SGD)"] = display_df["Amount (SGD)"].apply(lambda x: f"S${x:,.2f}")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        col_del1, col_del2 = st.columns([1, 2])
        with col_del1:
            del_id = st.number_input("Delete Entry by ID", min_value=1, step=1)
            if st.button("🗑️ Delete Selected Entry"):
                delete_expense(del_id)
                st.success(f"Deleted entry ID {del_id}")
                st.rerun()
    else:
        st.info("No expenses recorded yet.")

# ------------------------------------------------------------------------------
# TAB 3: SPATIAL MAP (100% FREE CARTO VECTOR TILES - NO API KEY REQUIRED)
# ------------------------------------------------------------------------------
with tab_map:
    st.markdown("#### Geographic Expense & Location Visualizer")
    
    if not df.empty and "latitude" in df.columns and "longitude" in df.columns:
        valid_map_df = df.dropna(subset=["latitude", "longitude"])
        
        if not valid_map_df.empty:
            # Gold Nodes Layer
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=valid_map_df,
                get_position="[longitude, latitude]",
                get_color="[212, 175, 55, 220]",
                get_radius=120,
                radius_min_pixels=6,
                radius_max_pixels=16,
                pickable=True,
                auto_highlight=True,
            )

            # Center Viewport on mean coordinates
            view_state = pdk.ViewState(
                latitude=valid_map_df["latitude"].mean(),
                longitude=valid_map_df["longitude"].mean(),
                zoom=12,
                pitch=20,
            )

            # Free Carto Dark Matter Style (No API Key required)
            deck = pdk.Deck(
                layers=[scatter_layer],
                initial_view_state=view_state,
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                tooltip={
                    "html": "<b>{description}</b><br/>Category: {category}<br/>Amount: S${amount_home} ({amount_foreign} {currency})<br/>Paid by: {paid_by}",
                    "style": {
                        "backgroundColor": "#12131A", 
                        "color": "#F8FAFC", 
                        "border": "1px solid rgba(255,255,255,0.1)", 
                        "borderRadius": "8px"
                    }
                }
            )
            st.pydeck_chart(deck, use_container_width=True)
        else:
            st.info("No locations to display on map.")
    else:
        st.info("No expenses logged yet to visualize on the map.")

# ------------------------------------------------------------------------------
# TAB 4: SETTLE UP & GROUP SPLIT (SGD BASE)
# ------------------------------------------------------------------------------
with tab_split:
    st.markdown("#### Group Split & Net Balances (in SGD)")
    
    if not df.empty and members:
        total_sgd_spent = df["amount_home"].sum()
        split_per_person = total_sgd_spent / len(members)
        
        c_split1, c_split2 = st.columns(2)
        c_split1.markdown(f"""
        <div class="glass-panel">
            <div style="font-size: 11px; text-transform: uppercase; color: #94A3B8; font-weight: 600;">Total Group Spend</div>
            <div style="font-family: 'JetBrains Mono'; font-size: 24px; font-weight: 600; color: #D4AF37; margin-top: 4px;">S${total_sgd_spent:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c_split2.markdown(f"""
        <div class="glass-panel">
            <div style="font-size: 11px; text-transform: uppercase; color: #94A3B8; font-weight: 600;">Equal Share Per Person</div>
            <div style="font-family: 'JetBrains Mono'; font-size: 24px; font-weight: 600; color: #38BDF8; margin-top: 4px;">S${split_per_person:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        paid_totals = df.groupby("paid_by")["amount_home"].sum().to_dict()
        
        summary_data = []
        for m in members:
            paid = paid_totals.get(m, 0.0)
            balance = paid - split_per_person
            summary_data.append({
                "Member": m,
                "Total Paid (SGD)": f"${paid:,.2f}",
                "Fair Share (SGD)": f"${split_per_person:,.2f}",
                "Net Balance (SGD)": f"${balance:+,.2f}",
                "Status": "✦ Gets back money" if balance > 0.01 else "✦ Owes money" if balance < -0.01 else "✓ Settled"
            })
            
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
    else:
        st.info("Add expenses and group members to calculate fair splits.")
