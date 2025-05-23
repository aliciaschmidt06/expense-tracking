import streamlit as st

from src.manage_csvs import manage_csvs_page
from src.spending_plan import conscious_spending_plan
from src.average_spending import average_spending
from src.raw_data_viewer import raw_data_viewer
from src.manage_money_owed import manage_money_owed
from src.constants import *
from src.backend import (
    load_config_file,
    show_repeated_charges,
    update_categories_config
)
from src.database import (
    bootstrap_database,
    get_dataframe_from_database,
    refresh_database
)

# Load config
category_config = load_config_file(CATEGORY_CONFIG_PATH)

#Initialize database
if 'db_bootstrapped' not in st.session_state:
    bootstrap_database(DATA_FOLDER, category_config)
    st.session_state.db_bootstrapped = True

# Sidebar navigation
st.sidebar.title("📊 Navigation")
view = st.sidebar.radio("Go to", [
    "💰 Conscious Spending",
    "📊 Average Spending",
    "🔁 Repeated Charges",
    "🛠 Config Editor",
    "📋 Raw Data",
    "📤 Upload Expense Data (.csv)",
    "💸 Manage Money Owed"
])

# ---- View: Upload CSV Files ----
if view == "📤 Upload Expense Data (.csv)":
    manage_csvs_page(category_config)
    
# ---- View: Spending Plan ----
elif view == "💰 Conscious Spending":
    df = get_dataframe_from_database()
    conscious_spending_plan(df, category_config)

# ---- View: Spending Plan ----
elif view == "📊 Average Spending":
    df = get_dataframe_from_database()
    average_spending(df, category_config)

# ---- View: Repeated Charges ----
elif view == "🔁 Repeated Charges":
    df = get_dataframe_from_database()
    st.title("🔁 Repeated Charges")
    st.dataframe(show_repeated_charges(df))

# ---- View: Config Editor ----
elif view == "🛠 Config Editor":
    update_categories_config(CATEGORY_CONFIG_PATH)

    if st.button("🔄 Refresh Database (Delete & Re-Bootstrap)"):
        with st.spinner("Refreshing database..."):
            refresh_database(DATA_FOLDER, category_config)
        st.success("Database has been refreshed.")

# ---- View: Raw Data ----
elif view == "📋 Raw Data":
    df = get_dataframe_from_database()
    raw_data_viewer(df, category_config)

#---- View: Manage Money Owed ----
elif view == "💸 Manage Money Owed":
    manage_money_owed(category_config)
   