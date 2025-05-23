import streamlit as st
import os
import pandas as pd
from src.constants import *
from src.database import *

def manage_csvs_page(category_config):
    st.title("📤 Upload & Manage Expense Data")

    # Initialize state if needed
    if "included_files" not in st.session_state:
        st.session_state.included_files = sorted(
            [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
        )
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()

    # Upload a CSV
    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded_file is not None:
        filename = uploaded_file.name
        filepath = os.path.join(DATA_FOLDER, filename)

        if filename not in st.session_state.processed_files:
            # Save the file
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"{filename} uploaded successfully.")

            # Update session state
            if filename not in st.session_state.included_files:
                st.session_state.included_files.append(filename)
            st.session_state.processed_files.add(filename)

            # Update the database ONCE for this upload
            update_database("add", filename, category_config)
            st.success("Database updated with uploaded file.")

    # Optional file deletion
    all_csvs = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")])
    st.markdown("### 🗑️ Delete CSV Files")
    files_to_delete = st.multiselect("Select files to delete:", all_csvs)
    if st.button("Delete Selected Files"):
        for file in files_to_delete:
            os.remove(os.path.join(DATA_FOLDER, file))
            update_database("remove", file, category_config)
            if file in st.session_state.included_files:
                st.session_state.included_files.remove(file)
            if file in st.session_state.processed_files:
                st.session_state.processed_files.remove(file)
        st.success("Files deleted.")
        st.rerun()

    # Show updated data
    st.markdown("### 🔍 Current Database View")
    db_df = get_dataframe_from_database()
    st.dataframe(db_df, use_container_width=True)