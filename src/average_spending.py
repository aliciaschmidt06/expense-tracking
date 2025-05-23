import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

from src.backend import parse_date_input
from src.constants import *

def average_spending(df, category_config):
    st.title("📊 Average Spending")

    user_input = st.text_input(
        "Enter month, year or date range (e.g. 'Jan 2024', '2024', 'Jan 2024 to Mar 2024')"
    )
    interval = st.radio("Averaging Interval", ["Monthly", "Weekly", "Daily"])

    try:
        start_date, end_date, is_year_only = parse_date_input(user_input)
    except Exception as e:
        st.warning(str(e))
        return

    df[DATE_STR] = pd.to_datetime(df[DATE_STR])

    if is_year_only:
        filtered = df[df[DATE_STR].dt.year == start_date.year].copy()
        end_date = pd.Timestamp(f"{start_date.year}-12-31")
    elif end_date:
        filtered = df[(df[DATE_STR] >= start_date) & (df[DATE_STR] <= end_date)].copy()
    else:
        filtered = df[(df[DATE_STR].dt.month == start_date.month) & (df[DATE_STR].dt.year == start_date.year)].copy()
        end_date = start_date + pd.offsets.MonthEnd(0)

    if filtered.empty:
        st.warning("No transactions found in the selected time range.")
        return

    # Determine time delta in days/months/weeks
    delta_days = (end_date - start_date).days + 1
    if interval == "Daily":
        divisor = delta_days
    elif interval == "Weekly":
        divisor = max(1, round(delta_days / 7))
    else:  # Monthly
        rd = relativedelta(end_date, start_date)
        divisor = rd.years * 12 + rd.months + 1  # Inclusive of start & end month

    st.markdown(f"### From {start_date.date()} to {end_date.date()} ({divisor} {interval.lower()}s)")

    # Normalize numeric fields
    filtered[EXPENSE_STR] = pd.to_numeric(filtered[EXPENSE_STR].fillna(0), errors="coerce")
    filtered[INCOME_STR] = pd.to_numeric(filtered[INCOME_STR].fillna(0), errors="coerce")

    # --- EXPENSES ---
    valid_expense_categories = set(category_config.get("spending_categories", {}).keys())

    avg_expenses = (
        filtered[filtered[CATEGORY_STR].isin(valid_expense_categories)]
        .groupby(CATEGORY_STR)[EXPENSE_STR]
        .sum()
        .div(divisor)
        .sort_values(ascending=False)
    )

    st.subheader(f"📉 Average Expenses per Category ({interval.lower()})")
    if not avg_expenses.empty:
        for cat, val in avg_expenses.items():
            st.markdown(f"**{cat}**: ${val:.2f}")
    else:
        st.info("No categorized expense transactions found.")

    # --- INCOME ---
    valid_income_categories = set(["income", "uncategorized"])  # adjust if you use more income categories

    income_data = filtered[filtered[INCOME_STR] > 0]
    income_by_category = (
        income_data[income_data[CATEGORY_STR].isin(valid_income_categories)]
        .groupby(CATEGORY_STR)[INCOME_STR]
        .sum()
        .div(divisor)
        .sort_values(ascending=False)
    )

    st.subheader(f"💰 Average Income per Category ({interval.lower()})")
    if not income_by_category.empty:
        for cat, val in income_by_category.items():
            st.markdown(f"**{cat}**: ${val:.2f}")
    else:
        st.info("No income transactions found in the selected range.")