import os
import sqlite3
import pandas as pd
from constants import *

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_transactions_table():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                date TEXT,
                place TEXT,
                expense REAL,
                income REAL,
                credit_card TEXT,
                account TEXT,
                category TEXT,
                source_file TEXT,
                active INTEGER,
                UNIQUE(date, place, expense, income, credit_card, account)
            )
        ''')
        conn.commit()

def categorize_transaction(place, config):
    place_lower = place.lower()
    # Check income
    for keyword in config.get("income", {}).get("keywords", []):
        if keyword in place_lower:
            return "income"
    # Check spending
    for category, details in config.get("spending_categories", {}).items():
        for keyword in details.get("keywords", []):
            if keyword in place_lower:
                return category
    return "uncategorized"

def update_database(mode, csv_filename, config):
    full_path = os.path.join(DATA_FOLDER, csv_filename)
    filename = os.path.basename(full_path)
    account_name = os.path.splitext(filename)[0]  # Remove .csv extension

    if mode not in {"add", "remove", "deactivate"}:
        print(f"Unsupported mode: {mode}")
        return

    # Handle remove
    if mode == "remove":
        with get_connection() as conn:
            conn.execute("DELETE FROM transactions WHERE source_file = ?", (filename,))
            conn.commit()
            conn.execute("VACUUM")
        print(f"Database removed rows from file: {filename}")
        return

    # Handle deactivate
    if mode == "deactivate":
        with get_connection() as conn:
            conn.execute("UPDATE transactions SET active = 0 WHERE source_file = ?", (filename,))
            conn.commit()
        print(f"Database deactivated rows from file: {filename}")
        return

    # Handle add
    column_names = [DATE_STR, PLACE_STR, EXPENSE_STR, INCOME_STR, "credit_card"]

    if not os.path.isfile(full_path):
        print(f"File not found: {full_path}")
        return

    try:
        df = pd.read_csv(full_path, header=None, names=column_names)
    except Exception as e:
        print(f"Failed to read CSV: {full_path}\nError: {e}")
        return

    required_cols = [DATE_STR, PLACE_STR, EXPENSE_STR, INCOME_STR, "credit_card"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"CSV file {full_path} missing required columns: {missing_cols}")
        return

    df = df.dropna(subset=[EXPENSE_STR, INCOME_STR], how='all')

    df[CATEGORY_STR] = df[PLACE_STR].apply(lambda place: categorize_transaction(place, config))
    df["source_file"] = filename
    df[ACCOUNT_STR] = account_name

    with get_connection() as conn:
         for _, row in df.iterrows():
            # Check if the row already exists and is inactive
            existing = conn.execute('''
                SELECT active FROM transactions
                WHERE date = ? AND place = ? AND expense = ? AND income = ? AND credit_card = ? AND source_file = ?
            ''', (
                row[DATE_STR], row[PLACE_STR], row[EXPENSE_STR], row[INCOME_STR],
                row["credit_card"], row["source_file"]
            )).fetchone()

            if existing is not None:
                if existing[0] == 0:
                    # Row exists but is inactive — skip it (do not reactivate)
                    continue
                else:
                    # Row already exists and is active — skip as well
                    continue
            try:
                conn.execute('''
                    INSERT INTO transactions
                    (date, place, expense, income, credit_card, account, category, source_file, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row[DATE_STR], row[PLACE_STR], row[EXPENSE_STR], row[INCOME_STR],
                    row["credit_card"], row[ACCOUNT_STR], row[CATEGORY_STR], row["source_file"], 1
                ))
            except Exception as e:
                print(f"Error inserting row from {filename}: {e}")
    print(f"Database added file: {filename}")

def bootstrap_database(data_folder, config):
    create_transactions_table()
    for file in os.listdir(data_folder):
        if file.endswith(".csv"):
            update_database("add", file, config)

def get_dataframe_from_database():
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM transactions WHERE active = 1", conn)
    return df

def update_transaction_category_db(transaction_id, new_category):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE transactions
                SET category = ?
                WHERE id = ? AND active = 1
            """, (new_category, transaction_id))
            
            if cursor.rowcount == 0:
                print(f"No active transaction found with ID {transaction_id}")
            else:
                print(f"Updated transaction ID {transaction_id} to category '{new_category}'")

            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error while updating category: {e}")
