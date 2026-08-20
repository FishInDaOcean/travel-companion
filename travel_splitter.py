import streamlit as st
import pandas as pd
import sqlite3
import requests
from datetime import date

# Database Setup
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
            expense_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_expense(desc, amt_foreign, curr, rate, paid_by, category, exp_date):
    amt_home = amt_foreign / rate if rate > 0 else amt_foreign
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (description, amount_foreign, currency, exchange_rate, amount_home, paid_by, category, expense_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (desc, amt_foreign, curr, rate, round(amt_home, 2), paid_by, category, exp_date))
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

# Cached Live Exchange Rate Fetcher (Refreshes once per hour)
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
    # Fallback rates if offline or API unreachable
    fallback = {
        "JPY": 115.0, "MYR": 3.48, "THB": 26.8, "TWD": 24.2,
        "KRW": 1025.0, "USD": 0.76, "EUR": 0.70, "GBP": 0.60,
        "VND": 19000.0, "IDR": 12000.0, "AUD": 1.15
    }
    return fallback, "Offline Mode (Fallback)"

init_db()

st.set_page_config(page_title="Trip Expense & Splitter (SGD)", layout="wide")
st.title("🇸🇬 Overseas Travel Budget & Splitter")

# Fetch Live Rates based on SGD
rates_dict, status_msg = fetch_live_rates("SGD")

# Sidebar Configuration
st.sidebar.header("⚙️ Currency & Live Rates")
st.sidebar.caption(f"Status: **{status_msg}**")

home_curr = "SGD"
popular_currencies = ["JPY", "MYR", "THB", "TWD", "KRW", "USD", "EUR", "GBP", "VND", "IDR", "AUD", "Other"]
selected_foreign = st.sidebar.selectbox("Destination Currency", popular_currencies, index=0)

if selected_foreign == "Other":
    foreign_curr = st.sidebar.text_input("Enter Currency Code (e.g. CHF, NZD)", value="EUR").upper()
else:
    foreign_curr = selected_foreign

# Auto-populate exchange rate from live data
default_live_rate = float(rates_dict.get(foreign_curr, 1.0))

rate = st.sidebar.number_input(
    f"Exchange Rate (1 {home_curr} = X {foreign_curr})",
    value=default_live_rate,
    format="%.4f"
)

st.sidebar.markdown("---")
st.sidebar.header("👥 Group Members")
members_str = st.sidebar.text_input("Names (comma-separated)", value="Me, Alex, Jordan")
members = [m.strip() for m in members_str.split(",") if m.strip()]

# Quick Offline Converter Widget
st.sidebar.markdown("---")
st.sidebar.header("⚡ Quick Price Converter")
calc_foreign = st.sidebar.number_input(f"Price in {foreign_curr}", value=1000.0, step=100.0)
st.sidebar.success(f"≈ **{(calc_foreign / rate):.2f} SGD**")

# Main Interface Tabs
tab1, tab2, tab3 = st.tabs(["➕ Add Expense", "📊 Trip Breakdown", "🤝 Settle Up & Bill Split"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        desc = st.text_input("Description", placeholder="e.g., Ichiran Ramen, Tokyo Metro Pass")
        amt = st.number_input(f"Amount in {foreign_curr}", min_value=0.0, step=10.0)
        category = st.selectbox("Category", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Other"])
    with col2:
        payer = st.selectbox("Paid By", members if members else ["Me"])
        exp_date = st.date_input("Date", value=date.today())
        
        st.write("")
        cost_in_sgd = amt / rate if rate > 0 else 0.0
        st.info(f"Equivalent Cost: **{cost_in_sgd:,.2f} SGD** (at 1 SGD = {rate} {foreign_curr})")
        
        if st.button("Save Expense", use_container_width=True):
            if desc and amt > 0:
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date))
                st.success(f"Logged: {desc} ({amt:,.0f} {foreign_curr} ≈ {cost_in_sgd:,.2f} SGD)")
                st.rerun()
            else:
                st.warning("Please provide a description and amount.")

df = get_expenses()

with tab2:
    if not df.empty:
        total_foreign = df["amount_foreign"].sum()
        total_sgd = df["amount_home"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Spent (Foreign)", f"{total_foreign:,.2f} {foreign_curr}")
        m2.metric("Total Spent (SGD)", f"${total_sgd:,.2f} SGD")
        m3.metric("Total Expenses Logged", len(df))
        
        st.markdown("---")
        st.subheader("Expense History")
        
        display_df = df[["id", "expense_date", "description", "category", "amount_foreign", "currency", "amount_home", "paid_by"]]
        display_df = display_df.rename(columns={"amount_home": "amount_sgd"})
        st.dataframe(display_df, use_container_width=True)
        
        del_id = st.number_input("Delete Entry ID", min_value=1, step=1)
        if st.button("🗑️ Delete Selected Entry"):
            delete_expense(del_id)
            st.rerun()
    else:
        st.info("No expenses recorded yet.")

with tab3:
    st.subheader("Group Split & Balances (in SGD)")
    if not df.empty and members:
        total_sgd_spent = df["amount_home"].sum()
        split_per_person = total_sgd_spent / len(members)
        
        st.write(f"**Total Group Spend:** `${total_sgd_spent:,.2f} SGD`")
        st.write(f"**Equal Share Per Person:** `${split_per_person:,.2f} SGD`")
        st.markdown("---")
        
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
                "Status": "Gets back money" if balance > 0.01 else "Owes money" if balance < -0.01 else "Settled"
            })
            
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
    else:
        st.info("Add expenses and group members to calculate fair splits.")
