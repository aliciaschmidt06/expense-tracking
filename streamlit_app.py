import streamlit as st
import os
import yaml
import pandas as pd
from backend import *
from database import (
    initialize_database,
    update_database_with_new_data,
    update_transaction_category_db,
    get_data_from_database,
)

# Constants
CONFIG_PATH = "config.yaml"
DATA_FOLDER = "data"

os.makedirs(DATA_FOLDER, exist_ok=True)

# Load config
if not os.path.exists(CONFIG_PATH):
    st.error(f"Missing configuration file: {CONFIG_PATH}")
    st.stop()

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

# Sidebar navigation
st.sidebar.title("📊 Navigation")
view = st.sidebar.radio("Go to", [
    "💰 Spending Plan",
    "🔁 Repeated Charges",
    "🛠 Config Editor",
    "📋 Raw Data",
    "📤 Upload Expense Data (.csv)",
    "💸 Manage Money Owed"
])

# Initialize DB
initialize_database()

# ---- View: Upload CSV Files ----
if view == "📤 Upload Expense Data (.csv)":
    st.title("📤 Upload & Manage Expense Data")

    # Upload a CSV
    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_file is not None:
        filename = uploaded_file.name
        filepath = os.path.join(DATA_FOLDER, filename)
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"{filename} uploaded successfully (overwritten if it existed).")
        st.session_state.upload_trigger = True

    # Manage which files are included
    all_csvs = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')])
    if "included_files" not in st.session_state:
        st.session_state.included_files = all_csvs

    selected_files = st.multiselect(
        "Include these files in your analysis:",
        options=all_csvs,
        default=st.session_state.included_files
    )

    if set(selected_files) != set(st.session_state.included_files):
        st.session_state.included_files = selected_files
        st.session_state.include_trigger = True

    # Optional file deletion
    st.markdown("### 🗑️ Delete CSV Files")
    files_to_delete = st.multiselect("Select files to delete:", all_csvs)
    if st.button("Delete Selected Files"):
        for f in files_to_delete:
            os.remove(os.path.join(DATA_FOLDER, f))
        st.success("Files deleted. Please re-upload if needed.")
        st.rerun()

    # Update database if upload or inclusion changed
    if st.session_state.get("upload_trigger") or st.session_state.get("include_trigger"):
        update_database_with_new_data(
            selected_files=st.session_state.included_files,
            config=config
        )
        st.session_state.upload_trigger = False
        st.session_state.include_trigger = False
        st.success("Database updated with current files.")

    # Show updated data
    st.markdown("### 🔍 Current Database View")
    db_df = get_data_from_database()
    st.dataframe(db_df, use_container_width=True)

# ---- View: Spending Plan ----
elif view == "💰 Conscious Spending Plan":
    df = read_and_tag_csv_files(DATA_FOLDER, config)
    conscious_spending_plan_streamlit(df, config)

# ---- View: Repeated Charges ----
elif view == "🔁 Repeated Charges":
    df = read_and_tag_csv_files(DATA_FOLDER, config)
    st.title("🔁 Repeated Charges")
    st.dataframe(show_repeated_charges(df))

# ---- View: Config Editor ----
elif view == "🛠 Config Editor":
    update_config_streamlit(CONFIG_PATH)

# ---- View: Raw Data ----
elif view == "📋 Raw Data":
    df = read_and_tag_csv_files(DATA_FOLDER, config)
    st.title("📋 Raw Transaction Data")

    df = df.reset_index(drop=True)
    df["RowID"] = df.index

    # Show the data
    st.dataframe(df, use_container_width=True)

    # Allow the user to select a row by its index
    selected_index = st.selectbox("Select a row to modify", options=df["RowID"], format_func=lambda i: f"{i}: {df.iloc[i]['Place']}")

    if selected_index is not None:
        selected_transaction = df.iloc[selected_index]

        st.markdown("### 🏷️ Modify Category for Selected Row")
        predefined_categories = sorted( list(config.get("spending_categories", {}).keys()) + ["income"])

        new_category = st.selectbox(
            "Select new category",
            options=predefined_categories,
            index=0 if predefined_categories else None
        )

        if st.button("Modify Category"):
            success = update_transaction_category_db(selected_transaction, new_category) and update_transaction_category_config(new_category, selected_transaction["Place"], CONFIG_PATH)
            if success:
                st.success("Category updated in DB and config.")
                st.rerun()

#---- View: Manage Money Owed ----
elif view == "💸 Manage Money Owed":

   # Step 1: Category and date filtering
    categories = ["-- Any --"] + sorted(list(config.get("spending_categories", {}).keys()) + ["income"])
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

    expenses = load_data(category_filter=category_filter, date_range=date_filter)
    expenses = expenses.copy()  # avoid mutating shared dataframe
    expenses['selected'] = False

    st.subheader("Matching Expenses")
    if not expenses.empty:
        edited_df = st.data_editor(expenses[['id', 'Date', 'Expense', 'Place', 'selected']],
                                num_rows="dynamic", use_container_width=True, hide_index=True)
        selected_ids = edited_df[edited_df['selected'] == True]['id'].tolist()
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
                selected_df = expenses[expenses['id'].isin(selected_ids)]
                for transaction in selected_df.to_dict(orient='records'):
                    # Clean the 'Place' field to use only the part before the first comma
                    if isinstance(transaction['Place'], str) and ',' in transaction['Place']:
                        transaction['Place'] = transaction['Place'].split(',')[0].strip()

                    update_transaction_category_db(transaction, new_category)
                    update_transaction_category_config(new_category, transaction['Place'], CONFIG_PATH)

                st.success(f"Assigned {len(selected_ids)} transactions to '{new_category}' and updated config.")
            else:
                st.warning("No transactions selected.")
    else:
        st.info("Enter a trip name to enable assignment.")

    # Contact editor
    with st.expander("➕ Edit Contacts"):
            contact_names = [c["name"] for c in load_contacts()]
            new_contact_name = st.text_input("Add new contact name")
            new_contact_text = st.text_input("Contact text to look for in transfers")
            if st.button("Add Contact"):
                if new_contact_name and new_contact_name not in contact_names:
                    update_contacts_config(new_contact_name, new_contact_text)
                    st.success(f"Added contact: {new_contact_name}")
                    st.rerun()
                elif not new_contact_name:
                    st.warning("Please enter a name.")
                else:
                    st.warning("Contact already exists.")

    # Step 3: Reimbursement tracking
    st.subheader("💸 Reimbursement Tracking")
    contact_names = [c["name"] for c in load_contacts()]
    contact = st.selectbox("Select Contact", options=contact_names)

    trip_category = st.session_state.get("current_trip_category")
    if contact and trip_category:
        trip_df = load_data(category_filter=trip_category)
        total_trip_expenses = trip_df['Expense'].sum()

        income_df  = load_data(category_filter="Income")
        after_date = income_df['Date'].min() if not income_df.empty else None
        if after_date:
            payments_df = get_reimbursement_transactions(income_df,from_who=contact, after_date=after_date)
            total_repaid = payments_df['Income'].sum()
        else:
            payments_df = pd.DataFrame()
            total_repaid = 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Owed", f"${total_trip_expenses:,.2f}")
        col2.metric("Paid Back", f"${total_repaid:,.2f}")
        col3.metric("Still Owed", f"${(total_trip_expenses - total_repaid):,.2f}")

        if not payments_df.empty:
            with st.expander("View Payment Transactions"):
                st.dataframe(payments_df[['date', 'amount', 'description']], use_container_width=True)
        else:
            st.info("No reimbursement transactions found.")
    elif contact:
        st.warning("Assign to a trip first to compute amounts.")
    else:
        st.info("Enter a contact name to calculate repayments.")