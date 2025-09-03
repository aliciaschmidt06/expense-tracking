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
    income_data = income_data.drop_duplicates(subset=[DATE_STR, PLACE_STR, INCOME_STR])

    if income_data.empty:
        st.warning("No income transactions found in the selected period.")
        return

    # Income inclusion mode
    option = st.radio(
        "Choose which income to include:",
        ["Include everything", "Employer only"]
    )

    # Employer filtering
    with open("configs/contacts.yaml", "r") as f:
        contacts = yaml.safe_load(f)
    employer_keywords = [c.get("keyword", "").lower()
                         for c in contacts.get("contacts", [])
                         if c.get("name", "").lower() == "employer"]
    employer_keywords.append("payroll")

    if option == "Include everything":
        included_income = income_data.copy()
    else:
        mask = income_data[PLACE_STR].str.lower().str.contains("|".join(employer_keywords), na=False)
        included_income = income_data[mask]

    total_income = included_income[INCOME_STR].sum()
    st.subheader(f"Total Included Income: ${total_income:.2f}")
    st.dataframe(included_income[[DATE_STR, PLACE_STR, INCOME_STR]])

    # --- Process expenses with visible bounds ---
    filtered[EXPENSE_STR] = pd.to_numeric(filtered[EXPENSE_STR].fillna(0), errors="coerce")
    expenses_by_category = filtered.groupby(CATEGORY_STR)[EXPENSE_STR].sum()

    for category, settings in config["spending_categories"].items():
        lower, upper = settings.get("target_range", [0, 0])
        spent = expenses_by_category.get(category, 0)
        pct = (spent / total_income) * 100 if total_income else 0
        st.markdown(
            f"#### {category.capitalize()}: ${spent:.2f} "
            f"({pct:.2f}% of income) | Target: {lower*100:.1f}% – {upper*100:.1f}%"
        )
        if lower * 100 <= pct <= upper * 100:
            st.success("✅ Within target")
        else:
            st.error("❌ Outside target")

        cat_df = filtered[(filtered[CATEGORY_STR] == category) & (filtered[EXPENSE_STR] > 0)]
        if not cat_df.empty:
            st.dataframe(cat_df[[DATE_STR, PLACE_STR, EXPENSE_STR]])

    # --- Uncategorized handling ---
    unknown_df = filtered[(filtered[CATEGORY_STR] == "uncategorized") & (filtered[EXPENSE_STR] > 0)]
    unc_total = unknown_df[EXPENSE_STR].sum()
    unc_pct = (unc_total / total_income) * 100 if total_income else 0
    st.markdown(f"### Uncategorized: ${unc_total:.2f} ({unc_pct:.2f}%)")

    if not unknown_df.empty:
        st.dataframe(unknown_df[[DATE_STR, PLACE_STR, EXPENSE_STR]])

        st.markdown("### Categorize Uncategorized Transactions")
        for idx, row in unknown_df.iterrows():
            label = f"{row[DATE_STR].date()} - {row[PLACE_STR]} - ${row[EXPENSE_STR]:.2f}"
            new_category = st.selectbox(
                f"Assign category for: {label}",
                ["-- skip --"] + list(config["spending_categories"].keys()),
                key=f"uncat_{idx}"
            )
            if new_category != "-- skip --":
                # Update the dataframe in memory
                filtered.at[idx, CATEGORY_STR] = new_category

                # Add the transaction's place as a keyword in config.yaml
                place_keyword = str(row[PLACE_STR]).strip()
                if place_keyword.lower() not in [k.lower() for k in config["spending_categories"][new_category]["keywords"]]:
                    config["spending_categories"][new_category]["keywords"].append(place_keyword)

        # Save updated config back to disk
        if st.button("💾 Save categorization updates"):
            with open(CATEGORY_CONFIG_PATH, "w") as f:
                yaml.safe_dump(config, f)
            st.success("Config.yaml updated with new keywords!")
