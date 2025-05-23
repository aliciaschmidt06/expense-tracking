import streamlit as st
import pandas as pd
import yaml

from src.constants import *
from src.backend import parse_date_input


def conscious_spending_plan(df, config):

    st.title("📅 Conscious Spending Plan")
    user_input = st.text_input("Enter month, year or date range (e.g. 'Jan 2024', '2024', 'Jan 2024 to Mar 2024')")

    try:
        start_date, end_date, is_year_only = parse_date_input(user_input)
    except Exception as e:
        st.warning(str(e))
        return

    df[DATE_STR] = pd.to_datetime(df[DATE_STR])

    if is_year_only:
        filtered = df[df[DATE_STR].dt.year == start_date.year]
    elif end_date:
        filtered = df[(df[DATE_STR] >= start_date) & (df[DATE_STR] <= end_date)]
    else:
        filtered = df[(df[DATE_STR].dt.month == start_date.month) & (df[DATE_STR].dt.year == start_date.year)]

    # Remove internal transfers
    filtered = filtered[~((filtered[ACCOUNT_STR].isin(["checking", "savings"])) &
                          filtered[PLACE_STR].str.contains("Internet Banking INTERNET TRANSFER", case=False, na=False))]

    # Filter income data
    income_data = filtered[filtered[INCOME_STR] > 0]
    income_data = income_data[
        ~income_data[PLACE_STR].str.contains("THANK YOU", case=False, na=False) &
        ~income_data[PLACE_STR].str.contains("Internet Banking INTERNET TRANSFER 000000114295", case=False, na=False)
    ]

    if income_data.empty:
        st.warning("No income transactions found in the selected period.")
        return

    st.markdown("### Income Transactions")
    income_data["Include"] = False  # default

    # Automatically include "payroll" income
    income_data.loc[income_data[CATEGORY_STR].str.contains("payroll", case=False, na=False),  "Include"] = True

    # Let user choose to include other income transactions
    for idx, row in income_data.iterrows():
        is_payroll = "payroll" in str(row[CATEGORY_STR]).lower()
        label = f"{row[DATE_STR].date()} - {row[PLACE_STR]} - ${row[INCOME_STR]:.2f}"
        include = st.checkbox(label, key=f"income_{idx}", value=is_payroll)
        income_data.at[idx, "Include"] = include

    # Calculate total income
    included_income = income_data[income_data["Include"] == True]
    total_income = included_income[INCOME_STR].sum()
    st.subheader(f"Total Included Income: ${total_income:.2f}")
    st.dataframe(included_income[[DATE_STR, PLACE_STR, INCOME_STR]])

    # Process expenses
    filtered[EXPENSE_STR] = pd.to_numeric(filtered[EXPENSE_STR].fillna(0), errors='coerce')
    expenses_by_category = filtered.groupby(CATEGORY_STR)[EXPENSE_STR].sum()

    for category, settings in config["spending_categories"].items():
        lower, upper = settings.get("target_range", [0, 0])
        spent = expenses_by_category.get(category, 0)
        pct = (spent / total_income) * 100 if total_income else 0
        within_target = lower * 100 <= pct <= upper * 100
        st.markdown(f"#### {category.capitalize()}: ${spent:.2f} ({pct:.2f}% of income)")
        st.success("✅ Within target") if within_target else st.error("❌ Outside target")
        cat_df = filtered[(filtered[CATEGORY_STR] == category) & (filtered[EXPENSE_STR] > 0)]
        if not cat_df.empty:
            st.dataframe(cat_df[[DATE_STR, PLACE_STR, EXPENSE_STR]])

    # Uncategorized expenses
    unknown_df = filtered[(filtered[CATEGORY_STR] == "uncategorized") & (filtered[EXPENSE_STR] > 0)]
    unc_total = unknown_df[EXPENSE_STR].sum()
    unc_pct = (unc_total / total_income) * 100 if total_income else 0
    st.markdown(f"### Uncategorized: ${unc_total:.2f} ({unc_pct:.2f}%)")
    if not unknown_df.empty:
        st.dataframe(unknown_df[[DATE_STR, PLACE_STR, EXPENSE_STR]])