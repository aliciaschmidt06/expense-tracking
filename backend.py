import os
import pandas as pd
import yaml
import re
from datetime import datetime
from dateutil.parser import parse
from database import *
from constants import *


def parse_date_input(date_input):
    if re.match(r"^\d{4}$", date_input):
        return datetime.strptime(date_input, "%Y"), None, True  # year-only mode

    try:
        start_date = parse(date_input, fuzzy=True)
        return start_date, None, False  # single month mode
    except ValueError:
        pass

    range_match = re.match(r"^(.+?)\s+to\s+(.+?)$", date_input, re.IGNORECASE)
    if range_match:
        try:
            start_date = parse(range_match.group(1), fuzzy=True)
            end_date = parse(range_match.group(2), fuzzy=True)
            return start_date, end_date, False  # date range mode
        except ValueError:
            pass

    raise ValueError("Invalid date format. Please enter a valid month, year, or date range.")

def show_repeated_charges(df):
    df.columns = df.columns.str.strip().str.lower()
    exclude_keywords = ["Branch Transaction", "Internet Banking", "Electronic Funds Transfer", "WITHDRAWAL"]
    df_filtered = df[~df[PLACE_STR].str.contains('|'.join(exclude_keywords), case=False, na=False)]
    recurring = df_filtered.groupby([PLACE_STR, EXPENSE_STR]).filter(lambda x: len(x) > 1)
    return recurring.sort_values(by=[PLACE_STR, EXPENSE_STR])

def conscious_spending_plan(df, config):
    import streamlit as st

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

    filtered = filtered[~((filtered[ACCOUNT_STR].isin(["checking", "savings"])) &
                          filtered[PLACE_STR].str.contains("Internet Banking INTERNET TRANSFER", case=False, na=False))]

    income_data = filtered[filtered[INCOME_STR] > 0]
    income_data = income_data[
        ~income_data[PLACE_STR].str.contains("THANK YOU", case=False, na=False) &
        ~income_data[PLACE_STR].str.contains("Internet Banking INTERNET TRANSFER 000000114295", case=False, na=False)
    ]

    total_income = income_data[INCOME_STR].sum()
    st.subheader(f"Total Income: ${total_income:.2f}")

    if not income_data.empty:
        st.markdown("### Income Transactions")
        st.dataframe(income_data[[DATE_STR, PLACE_STR, INCOME_STR]])

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

    unknown_df = filtered[(filtered[CATEGORY_STR] == "unknown") & (filtered[EXPENSE_STR] > 0)]
    unc_total = unknown_df[EXPENSE_STR].sum()
    unc_pct = (unc_total / total_income) * 100 if total_income else 0
    st.markdown(f"### Uncategorized: ${unc_total:.2f} ({unc_pct:.2f}%)")
    if not unknown_df.empty:
        st.dataframe(unknown_df[[DATE_STR, PLACE_STR, EXPENSE_STR]])

def load_config_file(config_path=None):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    
    with open(config_path, "r") as file:
        try:
            config = yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML config: {e}")
    return config

def update_categories_config(config_path):
    import streamlit as st
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    st.title("✏️ Edit Category Rules")

    for cat, data in config["spending_categories"].items():
        with st.expander(f"Category: {cat}"):
            keywords = st.text_area(f"Keywords for '{cat}'", ", ".join(data.get("keywords", [])))
            lower = st.number_input(f"Lower bound % for '{cat}'", value=data.get("target_range", [0, 0])[0], format="%.2f")
            upper = st.number_input(f"Upper bound % for '{cat}'", value=data.get("target_range", [0, 0])[1], format="%.2f")
            config["spending_categories"][cat]["keywords"] = [k.strip().lower() for k in keywords.split(",") if k.strip()]
            config["spending_categories"][cat]["target_range"] = [lower, upper]

    if st.button("Save Config"):
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        st.success("Configuration saved!")
    
    return True

def update_transaction_category_config(category, place, config_path=None):
    if config_path is None:
        config_path = CATEGORY_CONFIG_PATH

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Normalize
    place = place.strip().lower()

    if category == INCOME_STR:
        keyword_list = config.setdefault(INCOME_STR, {}).setdefault("keywords", [])
    else:
        keyword_list = config.setdefault("spending_categories", {}).setdefault(category, {}).setdefault("keywords", [])

    # Add keyword if not already present
    if place not in keyword_list:
        keyword_list.append(place)

        # Save updated config
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f)

    return True

def get_contact_by_name(name, contacts):
    return next((c for c in contacts if c[NAME_STR] == name), None)

def get_contacts(config=None):
    return [c[NAME_STR] for c in load_config_file(config)]

def update_contacts_config(contacts, new_contact_name, new_contact_text):
    for contact in contacts:
        print({contact[NAME_STR]})

    if not any(c[NAME_STR] == new_contact_name for c in contacts):
        contacts.append({
            NAME_STR: new_contact_name,
            "keyword": new_contact_text
        })

        with open(CONTACTS_PATH, "w") as f:
            yaml.dump({"contacts": contacts}, f, default_flow_style=False)

def get_trip_expenses(df, start_date, end_date, category=None):
    df[DATE_STR] = pd.to_datetime(df[DATE_STR])
    mask = (df[DATE_STR] >= pd.to_datetime(start_date)) & (df[DATE_STR] <= pd.to_datetime(end_date))
    if category is not None:
        mask &= df[CATEGORY_STR] == category
    return df[mask].copy()

def get_reimbursement_transactions(df, from_who, after_date):
    df[DATE_STR] = pd.to_datetime(df[DATE_STR])
    return df[
        (df[DATE_STR] > pd.to_datetime(after_date)) &
        (df[INCOME_STR] > 0) &
        (df[PLACE_STR].str.contains(from_who, case=False, na=False))
    ]

def calculate_owed_amount(df):
    return df[EXPENSE_STR].sum()

def calculate_paid_amount(df):
    return df[INCOME_STR].sum()

def load_and_filter_data(category_filter=None, date_range=None):
    df = get_dataframe_from_database()

    if category_filter:
        df = df[df[CATEGORY_STR] == category_filter]

    if date_range:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df[DATE_STR] >= start_date) & (df[DATE_STR] <= end_date)]

    return df


