import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# Database Initialization
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

init_db()

st.set_page_config(page_title="Trip Expense & Splitter", layout="wide")
st.title("💱 Offline Overseas Travel Budget & Splitter")

# Sidebar: Currency & Exchange Rate Setup
st.sidebar.header("⚙️ Currency Settings (Offline)")
home_curr = st.sidebar.text_input("Home Currency", value="USD")
foreign_curr = st.sidebar.text_input("Travel Destination Currency", value="JPY")
rate = st.sidebar.number_input(f"Exchange Rate (1 {home_curr} = X {foreign_curr})", value=150.0, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("👥 Travel Group Members")
members_str = st.sidebar.text_input("Names (comma-separated)", value="Me, Alex, Jordan")
members = [m.strip() for m in members_str.split(",") if m.strip()]

# Quick Currency Converter Calculator
st.sidebar.markdown("---")
st.sidebar.header("⚡ Quick Price Converter")
calc_foreign = st.sidebar.number_input(f"Price in {foreign_curr}", value=1000.0, step=100.0)
st.sidebar.info(f"≈ **{calc_foreign / rate:.2f} {home_curr}**")

# Main Content Layout
tab1, tab2, tab3 = st.tabs(["➕ Add Expense", "📊 Trip Breakdown", "🤝 Settle Up & Bill Split"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        desc = st.text_input("Description", placeholder="e.g., Ramen Lunch, Metro Pass")
        amt = st.number_input(f"Amount in {foreign_curr}", min_value=0.0, step=10.0)
        category = st.selectbox("Category", ["Food & Dining", "Transport", "Accommodation", "Activities", "Shopping", "Other"])
    with col2:
        payer = st.selectbox("Paid By", members if members else ["Me"])
        exp_date = st.date_input("Date", value=date.today())
        
        st.write("")
        st.write(f"Estimated Cost: **{amt / rate:.2f} {home_curr}**")
        if st.button("Save Expense", use_container_width=True):
            if desc and amt > 0:
                log_expense(desc, amt, foreign_curr, rate, payer, category, str(exp_date))
                st.success(f"Logged {desc} ({amt:,.0f} {foreign_curr})")
                st.rerun()
            else:
                st.warning("Please provide a description and amount.")

df = get_expenses()

with tab2:
    if not df.empty:
        total_foreign = df["amount_foreign"].sum()
        total_home = df["amount_home"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Spent", f"{total_foreign:,.2f} {foreign_curr}")
        m2.metric("Total in Home Currency", f"{total_home:,.2f} {home_curr}")
        m3.metric("Total Entries", len(df))
        
        st.markdown("---")
        st.subheader("Expense History")
        
        display_df = df[["id", "expense_date", "description", "category", "amount_foreign", "amount_home", "paid_by"]]
        st.dataframe(display_df, use_container_width=True)
        
        del_id = st.number_input("Delete Entry ID", min_value=1, step=1)
        if st.button("🗑️ Delete Selected Entry"):
            delete_expense(del_id)
            st.rerun()
    else:
        st.info("No expenses recorded yet.")

with tab3:
    st.subheader("Group Split Summary")
    if not df.empty and members:
        total_home_spent = df["amount_home"].sum()
        split_per_person = total_home_spent / len(members)
        
        st.write(f"**Total Group Spend:** `{total_home_spent:,.2f} {home_curr}`")
        st.write(f"**Equal Share Per Person:** `{split_per_person:,.2f} {home_curr}`")
        st.markdown("---")
        
        # Calculate who paid what vs their fair share
        paid_totals = df.groupby("paid_by")["amount_home"].sum().to_dict()
        
        summary_data = []
        for m in members:
            paid = paid_totals.get(m, 0.0)
            balance = paid - split_per_person
            summary_data.append({
                "Member": m,
                f"Total Paid ({home_curr})": round(paid, 2),
                f"Fair Share ({home_curr})": round(split_per_person, 2),
                f"Balance ({home_curr})": round(balance, 2),
                "Status": "Gets back money" if balance > 0 else "Owes money" if balance < 0 else "Settled"
            })
            
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
    else:
        st.info("Add some expenses and members to calculate balances.")