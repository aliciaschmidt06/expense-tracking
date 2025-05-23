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
    interval = st.radio("Averaging Interval", ["Yearly", "Monthly", "Weekly", "Daily", "All Time (divisor = 1)"])

    try:
        start_date, end_date, is_year_only = parse_date_input(user_input)
    except Exception as e:
        st.warning(str(e))
        return

    df[DATE_STR] = pd.to_datetime(df[DATE_STR])

    if is_year_only:
        year_df = df[df[DATE_STR].dt.year == start_date.year].copy()
        if year_df.empty:
            st.warning("No transactions found for the selected year.")
            return
        filtered = year_df
        actual_end_date = year_df[DATE_STR].max()
        start_date = pd.Timestamp(f"{start_date.year}-01-01")
        end_date = actual_end_date
    elif end_date:
        filtered = df[(df[DATE_STR] >= start_date) & (df[DATE_STR] <= end_date)].copy()
        if filtered.empty:
            st.warning("No transactions found in the selected range.")
            return
    else:
        month_df = df[(df[DATE_STR].dt.month == start_date.month) & (df[DATE_STR].dt.year == start_date.year)].copy()
        if month_df.empty:
            st.warning("No transactions found for the selected month.")
            return
        filtered = month_df
        actual_end_date = month_df[DATE_STR].max()
        start_date = pd.Timestamp(f"{start_date.year}-{start_date.month:02d}-01")
        end_date = actual_end_date

    delta_days = (end_date - start_date).days + 1

    if interval == "Daily":
        divisor = delta_days
    elif interval == "Weekly":
        divisor = max(1, round(delta_days / 7))
    elif interval == "Monthly":
        rd = relativedelta(end_date, start_date)
        divisor = rd.years * 12 + rd.months + 1
    elif interval == "Yearly":
        rd = relativedelta(end_date, start_date)
        divisor = rd.years + (1 if rd.months > 0 or rd.days > 0 else 0)
    else:  # All Time
        divisor = 1

    st.markdown(f"### From {start_date.date()} to {end_date.date()} ({'total' if interval == 'All Time' else f'{divisor} {interval.lower()}s'})")

    filtered[EXPENSE_STR] = pd.to_numeric(filtered[EXPENSE_STR].fillna(0), errors="coerce")
    filtered[INCOME_STR] = pd.to_numeric(filtered[INCOME_STR].fillna(0), errors="coerce")

    # --- EXPENSES ---
    valid_expense_categories = set(category_config.get("spending_categories", {}).keys())

    # FIXED: define which spending category keys are considered fixed
    fixed_category_keys = {"fixed"}
    fixed_expense_categories = valid_expense_categories.intersection(fixed_category_keys)

    expenses = (
        filtered[filtered[CATEGORY_STR].isin(valid_expense_categories)]
        .groupby(CATEGORY_STR)[EXPENSE_STR]
        .sum()
        .div(divisor)
        .sort_values(ascending=False)
    )

    # Normalize for reliable matching
    normalized_expenses = expenses.copy()
    normalized_expenses.index = normalized_expenses.index.str.lower().str.strip()
    fixed_categories_normalized = {cat.lower().strip() for cat in fixed_expense_categories}
    avg_fixed_spending = normalized_expenses[normalized_expenses.index.isin(fixed_categories_normalized)].sum()

    st.subheader(f"📉 {'Total' if interval == 'All Time' else 'Average'} Expenses per Category")
    if not expenses.empty:
        for cat, val in expenses.items():
            st.markdown(f"**{cat}**: ${val:.2f}")
    else:
        st.info("No categorized expense transactions found.")

    # --- INCOME ---
    valid_income_categories = set(["income", "uncategorized"])

    income_data = filtered[filtered[INCOME_STR] > 0]
    income_by_category = (
        income_data[income_data[CATEGORY_STR].isin(valid_income_categories)]
        .groupby(CATEGORY_STR)[INCOME_STR]
        .sum()
        .div(divisor)
        .sort_values(ascending=False)
    )

    st.subheader(f"💰 {'Total' if interval == 'All Time' else 'Average'} Income per Category")
    if not income_by_category.empty:
        for cat, val in income_by_category.items():
            st.markdown(f"**{cat}**: ${val:.2f}")
    else:
        st.info("No income transactions found in the selected range.")

    # --- TIP SECTION (Only for Monthly) ---
    if interval == "Monthly":
        payroll_income = income_data[income_data[PLACE_STR].str.lower().str.contains("payroll", na=False)]
        avg_payroll_monthly = payroll_income[INCOME_STR].sum() / divisor

        st.markdown(
            f"""
            <div style="background-color: #fff9db; padding: 1rem; border-radius: 0.5rem; border: 1px solid #f1e4b3;">
                <strong>⭐ Tip:</strong><br>
                Recomended emergency fund:<br><br>
                  <strong>3 months</strong> of paychecks: 3 × ${avg_payroll_monthly:.2f} = <strong>${avg_payroll_monthly * 3:.2f}</strong><br>
                  or at least
                  <strong>6 months</strong> of fixed spending: 6 × ${avg_fixed_spending:.2f} = <strong>${avg_fixed_spending * 6:.2f}</strong>
            </div>
            """,
            unsafe_allow_html=True
        )
