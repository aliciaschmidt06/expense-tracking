import streamlit as st
import pandas as pd

from src.constants import *
from src.backend import (
    load_and_filter_data, 
    update_transaction_category_config, 
    load_config_file, 
    update_contacts_config
    )
from src.database import update_transaction_category_db


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

def manage_money_owed(category_config):
    # Step 1: Category and date filtering
    categories = ["-- Any --"] + sorted(list(category_config.get("spending_categories", {}).keys()) + [INCOME_STR])
    selected_category = st.selectbox(
        "Select new category",
        options=categories,
        index=0 if categories else None
    )
    category_filter = None if selected_category == "-- Any --" else selected_category

    date_range = st.date_input("Optional Date Range Filter", [])
    if len(date_range) == 2:
        start_date = date_range[0]
        end_date = date_range[1]
        date_filter = (start_date, end_date)
    else:
        date_filter = None

    expenses = load_and_filter_data(category_filter=category_filter, date_range=date_filter)
    expenses = expenses.copy()  # avoid mutating shared dataframe
    expenses['selected'] = False

    st.subheader("Matching Expenses")
    if not expenses.empty:
        edited_df = st.data_editor(expenses[[ID_STR, DATE_STR, EXPENSE_STR, PLACE_STR, 'selected']],
                                num_rows="dynamic", use_container_width=True, hide_index=True)
        selected_ids = edited_df[edited_df['selected'] == True][ID_STR].tolist()
    else:
        st.info("No matching expenses found.")
        selected_ids = []

    # Step 2: Trip tagging
    st.subheader("Assign to Trip Category")
    new_trip_name = st.text_input("Trip Name (e.g. 'business-trip-NY-2025')")

    if new_trip_name:
        new_category = f"trip-{new_trip_name.strip().lower().replace(' ', '-')}"
        st.session_state['current_trip_category'] = new_category
        if st.button("Assign Selected to Trip"):
            if selected_ids:
                selected_df = expenses[expenses[ID_STR].isin(selected_ids)]
                for transaction in selected_df.to_dict(orient='records'):
                    # Clean the place field to use only the part before the first comma
                    if isinstance(transaction[PLACE_STR], str) and ',' in transaction[PLACE_STR]:
                        transaction[PLACE_STR] = transaction[PLACE_STR].split(',')[0].strip()

                    update_transaction_category_db(transaction, new_category)
                    update_transaction_category_config(new_category, transaction[PLACE_STR], CATEGORY_CONFIG_PATH)

                st.success(f"Assigned {len(selected_ids)} transactions to '{new_category}' and updated config.")
            else:
                st.warning("No transactions selected.")
    else:
        st.info("Enter a trip name to enable assignment.")

    # Contact editor
    contacts = load_config_file(CONTACTS_PATH)["contacts"]
    with st.expander("➕ Edit Contacts"):
            contact_names = [c["name"] for c in contacts]
            new_contact_name = st.text_input("Add new contact name")
            new_contact_text = st.text_input("Contact text to look for in transfers")
            if st.button("Add Contact"):
                if new_contact_name and new_contact_name not in contact_names:
                    update_contacts_config(contacts, new_contact_name, new_contact_text)
                    st.success(f"Added contact: {new_contact_name}")
                    st.rerun()
                elif not new_contact_name:
                    st.warning("Please enter a name.")
                else:
                    st.warning("Contact already exists.")

    # Step 3: Reimbursement tracking
    st.subheader("💸 Reimbursement Tracking")
    contact_names = [c["name"] for c in contacts]
    contact = st.selectbox("Select Contact", options=contact_names)

    trip_category = st.session_state.get("current_trip_category")
    if contact and trip_category:
        trip_df = load_and_filter_data(category_filter=trip_category)
        total_trip_expenses = trip_df[EXPENSE_STR].sum()

        income_df  = load_and_filter_data(category_filter="Income")
        after_date = income_df[DATE_STR].min() if not income_df.empty else None
        if after_date:
            payments_df = get_reimbursement_transactions(income_df,from_who=contact, after_date=after_date)
            total_repaid = payments_df[INCOME_STR].sum()
        else:
            payments_df = pd.DataFrame()
            total_repaid = 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Owed", f"${total_trip_expenses:,.2f}")
        col2.metric("Paid Back", f"${total_repaid:,.2f}")
        col3.metric("Still Owed", f"${(total_trip_expenses - total_repaid):,.2f}")

        if not payments_df.empty:
            with st.expander("View Payment Transactions"):
                st.dataframe(payments_df[[DATE_STR, 'amount', 'description']], use_container_width=True)
        else:
            st.info("No reimbursement transactions found.")
    elif contact:
        st.warning("Assign to a trip first to compute amounts.")
    else:
        st.info("Enter a contact name to calculate repayments.")