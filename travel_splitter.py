import streamlit as st
import pandas as pd
import pydeck as pdk
from datetime import datetime

# ==============================================================================
# 1. PAGE CONFIGURATION & LUXURY DESIGN SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="Vanguard — Travel Companion",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Design System: Obsidian & Champagne Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Global CSS Variables & Resets */
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

    /* Streamlit specific UI cleanup */
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

    /* Frosted Luxury Ribbon */
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
    .brand-accent {
        color: var(--accent-gold);
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

    /* Glass Cards */
    .glass-card {
        background: var(--card-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 16px;
        transition: border-color 0.2s ease;
    }
    .glass-card:hover {
        border-color: var(--border-hover);
    }

    /* Metric Cards */
    .metric-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 14px 18px;
    }
    .metric-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
        font-weight: 600;
    }
    .metric-value {
        font-size: 20px;
        font-weight: 600;
        color: var(--text-primary);
        font-family: 'JetBrains Mono', monospace;
        margin-top: 4px;
    }

    /* Timeline Nodes */
    .timeline-node {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 14px 16px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        margin-bottom: 10px;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .timeline-node:hover {
        background: rgba(255, 255, 255, 0.04);
        border-color: rgba(212, 175, 55, 0.35);
        transform: translateX(3px);
    }
    .node-time {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 600;
        color: var(--accent-gold);
        min-width: 50px;
        padding-top: 2px;
    }
    .node-title {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary);
    }
    .node-desc {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 2px;
    }
    .node-badge {
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.06);
        color: var(--text-secondary);
    }

    /* Input & Button Refinement */
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
        box-shadow: 0 0 20px var(--accent-gold-glow) !important;
        transform: translateY(-1px);
    }
    div.stButton > button:active {
        transform: translateY(0);
    }
    
    /* Streamlit Tabs Customization */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(18, 20, 29, 0.5);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border-subtle);
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
# 2. STATE MANAGEMENT & MOCK DATA
# ==============================================================================
if "itinerary" not in st.session_state:
    st.session_state.itinerary = [
        {"id": 1, "day": "Day 1 • Shibuya", "time": "09:30", "title": "Fuglen Tokyo", "category": "Café", "desc": "Artisan coffee & Norwegian pastries", "cost_jpy": 1200, "lat": 35.6669, "lon": 139.6917},
        {"id": 2, "day": "Day 1 • Shibuya", "time": "11:00", "title": "Yoyogi Park & Meiji Shrine", "category": "Culture", "desc": "Peaceful forest walk & sightseeing", "cost_jpy": 0, "lat": 35.6717, "lon": 139.6949},
        {"id": 3, "day": "Day 1 • Shibuya", "time": "14:00", "title": "Shibuya Sky Observation", "category": "Attraction", "desc": "Panoramic rooftop views (Entry ticket booked)", "cost_jpy": 2200, "lat": 35.6585, "lon": 139.7013},
        {"id": 4, "day": "Day 1 • Shibuya", "time": "18:30", "title": "Omoide Yokocho", "category": "Dining", "desc": "Yakitori & local izakaya dinner", "cost_jpy": 4500, "lat": 35.6932, "lon": 139.6997},
        {"id": 5, "day": "Day 2 • Ginza & TeamLab", "time": "10:00", "title": "Ginza Six & Rooftop", "category": "Shopping", "desc": "Architecture & art installations", "cost_jpy": 2500, "lat": 35.6696, "lon": 139.7640},
        {"id": 6, "day": "Day 2 • Ginza & TeamLab", "time": "14:30", "title": "teamLab Planets Toyosu", "category": "Attraction", "desc": "Immersive digital art exhibition", "cost_jpy": 3800, "lat": 35.6491, "lon": 139.7898},
    ]

if "expenses" not in st.session_state:
    st.session_state.expenses = [
        {"item": "Flight Tickets (SIN-NRT)", "amount_sgd": 680.0, "paid_by": "Alex", "category": "Transit"},
        {"item": "Boutique Hotel Shibuya (3 Nights)", "amount_sgd": 720.0, "paid_by": "You", "category": "Lodging"},
        {"item": "Shibuya Sky Tickets (x2)", "amount_sgd": 38.5, "paid_by": "Alex", "category": "Attraction"},
        {"item": "Dinner @ Omoide Yokocho", "amount_sgd": 78.8, "paid_by": "You", "category": "Dining"},
    ]

if "checklist" not in st.session_state:
    st.session_state.checklist = [
        {"item": "Passport & Visit Japan Web QR Code", "done": True, "cat": "Essentials"},
        {"item": "Suica Card added to Apple Wallet", "done": True, "cat": "Transit"},
        {"item": "Universal Travel Adapter & 65W GaN Charger", "done": False, "cat": "Electronics"},
        {"item": "eSIM / Roaming activated", "done": True, "cat": "Essentials"},
        {"item": "Cash exchange (50,000 JPY backup)", "done": False, "cat": "Finance"},
    ]

# Fixed exchange rate (1 SGD to JPY)
EXCHANGE_RATE_SGD_JPY = 114.20
TOTAL_BUDGET_SGD = 2500.0

# Calculate Total Expenses
total_spent_sgd = sum(e["amount_sgd"] for e in st.session_state.expenses)
remaining_budget_sgd = TOTAL_BUDGET_SGD - total_spent_sgd

# ==============================================================================
# 3. EXECUTIVE HEADER RIBBON
# ==============================================================================
st.markdown(f"""
<div class="luxury-ribbon">
    <div class="brand-title">
        <span class="brand-accent">✦</span> VANGUARD &nbsp;<span style="color:#475569; font-weight:400;">| &nbsp;Tokyo Autumn Expedition</span>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
        <div class="currency-ticker">1 SGD ≈ {EXCHANGE_RATE_SGD_JPY:.2f} JPY</div>
        <div style="font-size: 13px; color: #94A3B8;">Oct 12 – Oct 19, 2026</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Overview Metrics Strip
st.markdown(f"""
<div class="metric-container">
    <div class="metric-card">
        <div class="metric-label">Total Allocated Budget</div>
        <div class="metric-value">S${TOTAL_BUDGET_SGD:,.2f}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Total Expenses Tracked</div>
        <div class="metric-value" style="color: #D4AF37;">S${total_spent_sgd:,.2f}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Remaining Balance</div>
        <div class="metric-value" style="color: {'#34D399' if remaining_budget_sgd >= 0 else '#F87171'};">S${remaining_budget_sgd:,.2f}</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Active Itinerary Stops</div>
        <div class="metric-value">{len(st.session_state.itinerary)} Locations</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. WORKSPACE TABS (PROGRESSIVE DISCLOSURE)
# ==============================================================================
tab_itinerary, tab_expenses, tab_vault = st.tabs(["✦ Spatial Itinerary", "✦ Expense Splitter", "✦ Checklist & Vault"])

# ------------------------------------------------------------------------------
# TAB 1: ITINERARY & ZERO-KEY MAP
# ------------------------------------------------------------------------------
with tab_itinerary:
    col_timeline, col_map = st.columns([1, 1.35], gap="large")

    with col_timeline:
        st.markdown("#### Schedule & Stops")
        
        # Day Filter
        days = list(dict.fromkeys(item["day"] for item in st.session_state.itinerary))
        if not days:
            days = ["Day 1 • General"]
            
        selected_day = st.segmented_control(
            "Selected Day",
            options=days,
            default=days[0],
            label_visibility="collapsed"
        )

        filtered_stops = [item for item in st.session_state.itinerary if item["day"] == selected_day]

        # Render Timeline Items
        if filtered_stops:
            for item in filtered_stops:
                cost_sgd = item['cost_jpy'] / EXCHANGE_RATE_SGD_JPY
                cost_str = f"¥{item['cost_jpy']:,} (~S${cost_sgd:.1f})" if item['cost_jpy'] > 0 else "Free"
                st.markdown(f"""
                <div class="timeline-node">
                    <div class="node-time">{item['time']}</div>
                    <div style="flex-grow: 1;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="node-title">{item['title']}</span>
                            <span class="node-badge">{item['category']}</span>
                        </div>
                        <div class="node-desc">{item['desc']}</div>
                    </div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:12px; color:#D4AF37; font-weight:500;">
                        {cost_str}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No stops added for this day yet.")

        # Quick Inline Add Stop Modal / Expander
        with st.expander("+ Add Stop to Itinerary"):
            with st.form("new_stop_form", clear_on_submit=True):
                c1, c2 = st.columns([1, 1])
                new_time = c1.text_input("Time (HH:MM)", value="12:00")
                new_cat = c2.selectbox("Category", ["Dining", "Sightseeing", "Café", "Attraction", "Shopping", "Transit"])
                new_title = st.text_input("Place Name", placeholder="e.g. Tsukiji Outer Market")
                new_desc = st.text_input("Notes / Details", placeholder="e.g. Try fresh sashimi bowl")
                
                c3, c4, c5 = st.columns([1, 1, 1])
                new_cost = c3.number_input("Cost (JPY)", min_value=0, value=1500, step=100)
                new_lat = c4.number_input("Latitude", value=35.6655, format="%.4f")
                new_lon = c5.number_input("Longitude", value=139.7707, format="%.4f")
                
                submit_stop = st.form_submit_button("Add Stop to Timeline")
                if submit_stop and new_title:
                    new_item = {
                        "id": len(st.session_state.itinerary) + 1,
                        "day": selected_day,
                        "time": new_time,
                        "title": new_title,
                        "category": new_cat,
                        "desc": new_desc,
                        "cost_jpy": int(new_cost),
                        "lat": float(new_lat),
                        "lon": float(new_lon)
                    }
                    st.session_state.itinerary.append(new_item)
                    st.rerun()

    with col_map:
        st.markdown("#### Spatial Navigation (No API Key Required)")
        
        # Prepare Map Data
        map_df = pd.DataFrame(filtered_stops if filtered_stops else st.session_state.itinerary)
        
        if not map_df.empty:
            # Scatter Layer (Gold Nodes)
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_df,
                get_position="[lon, lat]",
                get_color="[212, 175, 55, 220]",
                get_radius=110,
                radius_min_pixels=6,
                radius_max_pixels=15,
                pickable=True,
                auto_highlight=True,
            )

            # Connected Route Path Layer
            path_data = [{"path": map_df[["lon", "lat"]].values.tolist()}]
            path_layer = pdk.Layer(
                "PathLayer",
                data=path_data,
                get_path="path",
                get_color="[212, 175, 55, 100]",
                width_scale=20,
                width_min_pixels=2,
            )

            # Viewport Center
            view_state = pdk.ViewState(
                latitude=map_df["lat"].mean(),
                longitude=map_df["lon"].mean(),
                zoom=12.5,
                pitch=25,
            )

            # 100% Free Carto Dark Matter Style (No API Key needed)
            deck = pdk.Deck(
                layers=[path_layer, scatter_layer],
                initial_view_state=view_state,
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                tooltip={"html": "<b>{title}</b><br/>{category} • {time}<br/>{desc}", "style": {"backgroundColor": "#12131A", "color": "#F8FAFC", "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px"}}
            )
            st.pydeck_chart(deck, use_container_width=True)
        else:
            st.info("No coordinates available to map.")

# ------------------------------------------------------------------------------
# TAB 2: EXPENSE TRACKER & SMART SPLITTER
# ------------------------------------------------------------------------------
with tab_expenses:
    col_exp_list, col_exp_calc = st.columns([1.2, 1], gap="large")

    with col_exp_list:
        st.markdown("#### Expense Ledger")
        
        # Display Expenses Table
        if st.session_state.expenses:
            exp_df = pd.DataFrame(st.session_state.expenses)
            exp_df["Amount (SGD)"] = exp_df["amount_sgd"].apply(lambda x: f"S${x:,.2f}")
            exp_df["Equiv (JPY)"] = exp_df["amount_sgd"].apply(lambda x: f"¥{int(x * EXCHANGE_RATE_SGD_JPY):,}")
            
            st.dataframe(
                exp_df[["item", "category", "paid_by", "Amount (SGD)", "Equiv (JPY)"]].rename(columns={
                    "item": "Description",
                    "category": "Category",
                    "paid_by": "Paid By"
                }),
                use_container_width=True,
                hide_index=True
            )
        
        # Add Expense
