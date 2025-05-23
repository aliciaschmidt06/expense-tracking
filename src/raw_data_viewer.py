import streamlit as st

from src.constants import *
from src.database import update_transaction_category_db
from src.backend import update_transaction_category_config


def raw_data_viewer(df, category_config):
    st.title("📋 Raw Transaction Data")

    df = df.reset_index(drop=True)
    df["RowID"] = df.index
    st.dataframe(df, use_container_width=True)

    # Allow the user to select a row by its index
    selected_index = st.selectbox("Select a row to modify", options=df["RowID"], format_func=lambda i: f"{i}: {df.iloc[i][PLACE_STR]}")

    if selected_index is not None:
        selected_transaction = df.iloc[selected_index]

        st.markdown("### 🏷️ Modify Category for Selected Row")
        predefined_categories = sorted( list(category_config.get("spending_categories", {}).keys()) + ["income"])

        new_category = st.selectbox(
            "Select new category",
            options=predefined_categories,
            index=0 if predefined_categories else None
        )

        if st.button("Modify Category"):
            success = update_transaction_category_db(selected_transaction, new_category) and update_transaction_category_config(new_category, selected_transaction[PLACE_STR], CATEGORY_CONFIG_PATH)
            if success:
                st.success("Category updated in DB and config.")
                st.rerun()