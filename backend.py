import os
import pandas as pd
import yaml
import re
from datetime import datetime
from dateutil.parser import parse
from database import initialize_database, update_database_with_new_data, get_data_from_database, categorize_transaction

CONTACTS_PATH = "contacts.yaml"
CATEG_CONFIG_PATH = "config.yaml"

def read_and_tag_csv_files(folder_path, config):
    initialize_database()
    update_database_with_new_data(config=config)
    df = get_data_from_database()
    return df 

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
    exclude_keywords = ["Branch Transaction", "Internet Banking", "Electronic Funds Transfer", "WITHDRAWAL"]
    df_filtered = df[~df["Place"].str.contains('|'.join(exclude_keywords), case=False, na=False)]
    recurring = df_filtered.groupby(["Place", "Expense"]).filter(lambda x: len(x) > 1)
    return recurring.sort_values(by=["Place", "Expense"])

def conscious_spending_plan_streamlit(df, config):
    import streamlit as st

    st.title("📅 Conscious Spending Plan")
    user_input = st.text_input("Enter month, year or date range (e.g. 'Jan 2024', '2024', 'Jan 2024 to Mar 2024')")

    try:
        start_date, end_date, is_year_only = parse_date_input(user_input)
    except Exception as e:
        st.warning(str(e))
        return

    df["Date"] = pd.to_datetime(df["Date"])

    if is_year_only:
        filtered = df[df["Date"].dt.year == start_date.year]
    elif end_date:
        filtered = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
    else:
        filtered = df[(df["Date"].dt.month == start_date.month) & (df["Date"].dt.year == start_date.year)]

    filtered = filtered[~((filtered["Account"].isin(["checking", "savings"])) &
                          filtered["Place"].str.contains("Internet Banking INTERNET TRANSFER", case=False, na=False))]

    income_data = filtered[filtered["Income"] > 0]
    income_data = income_data[
        ~income_data["Place"].str.contains("THANK YOU", case=False, na=False) &
        ~income_data["Place"].str.contains("Internet Banking INTERNET TRANSFER 000000114295", case=False, na=False)
    ]

    total_income = income_data["Income"].sum()
    st.subheader(f"Total Income: ${total_income:.2f}")

    if not income_data.empty:
        st.markdown("### Income Transactions")
        st.dataframe(income_data[["Date", "Place", "Income"]])

    filtered["Expense"] = pd.to_numeric(filtered["Expense"].fillna(0), errors='coerce')
    expenses_by_category = filtered.groupby("Category")["Expense"].sum()

    for category, settings in config["spending_categories"].items():
        lower, upper = settings.get("target_range", [0, 0])
        spent = expenses_by_category.get(category, 0)
        pct = (spent / total_income) * 100 if total_income else 0
        within_target = lower * 100 <= pct <= upper * 100
        st.markdown(f"#### {category.capitalize()}: ${spent:.2f} ({pct:.2f}% of income)")
        st.success("✅ Within target") if within_target else st.error("❌ Outside target")
        cat_df = filtered[(filtered["Category"] == category) & (filtered["Expense"] > 0)]
        if not cat_df.empty:
            st.dataframe(cat_df[["Date", "Place", "Expense"]])

    unknown_df = filtered[(filtered["Category"] == "unknown") & (filtered["Expense"] > 0)]
    unc_total = unknown_df["Expense"].sum()
    unc_pct = (unc_total / total_income) * 100 if total_income else 0
    st.markdown(f"### Uncategorized: ${unc_total:.2f} ({unc_pct:.2f}%)")
    if not unknown_df.empty:
        st.dataframe(unknown_df[["Date", "Place", "Expense"]])

def update_config_streamlit(config_path):
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
        config_path = CATEG_CONFIG_PATH

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Normalize
    place = place.strip().lower()

    if category == "income":
        keyword_list = config.setdefault("income", {}).setdefault("keywords", [])
    else:
        keyword_list = config.setdefault("spending_categories", {}).setdefault(category, {}).setdefault("keywords", [])

    # Add keyword if not already present
    if place not in keyword_list:
        keyword_list.append(place)

        # Save updated config
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f)

    return True

def load_contacts(path=CONTACTS_PATH):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return yaml.safe_load(f).get("contacts", [])

def get_contact_by_name(name, contacts):
    return next((c for c in contacts if c["name"] == name), None)

def get_contacts(config=None):
    return [c["name"] for c in load_contacts()]

def update_contacts_config(new_contact_name, new_contact_text):
    contacts = load_contacts()

    for contact in contacts:
        print({contact["name"]})

    if not any(c["name"] == new_contact_name for c in contacts):
        contacts.append({
            "name": new_contact_name,
            "keyword": new_contact_text
        })

        with open(CONTACTS_PATH, "w") as f:
            yaml.dump({"contacts": contacts}, f, default_flow_style=False)

def get_trip_expenses(df, start_date, end_date, category=None):
    df["Date"] = pd.to_datetime(df["Date"])
    mask = (df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))
    if category is not None:
        mask &= df["Category"] == category
    return df[mask].copy()

def get_reimbursement_transactions(df, from_who, after_date):
    df["Date"] = pd.to_datetime(df["Date"])
    return df[
        (df["Date"] > pd.to_datetime(after_date)) &
        (df["Income"] > 0) &
        (df["Place"].str.contains(from_who, case=False, na=False))
    ]

def calculate_owed_amount(df):
    return df["Expense"].sum()

def calculate_paid_amount(df):
    return df["Income"].sum()

def load_data(category_filter=None, date_range=None):
    df = get_data_from_database()

    if category_filter:
        df = df[df['Category'] == category_filter]

    if date_range:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

    return df


