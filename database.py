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

def update_database(mode, csv_path, config):
    filename = os.path.basename(csv_path)
    account_name = os.path.splitext(filename)[0]  # filename without extension, used as 'account'

    # CSV columns (no header in CSV)
    column_names = ["date", "place", "expense", "income", "credit_card"]

    df = pd.read_csv(csv_path, header=None, names=column_names)

    required_cols = ["date", "place", "expense", "income", "credit_card"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"CSV file {csv_path} missing required columns: {missing_cols}")
        return

    df = df.dropna(subset=required_cols)

    if mode == "remove":
        with get_connection() as conn:
            conn.execute("DELETE FROM transactions WHERE source_file = ?", (filename,))
            conn.commit()
        return

    df["category"] = df["place"].apply(lambda place: categorize_transaction(place, config))
    df["source_file"] = filename
    df[ACCOUNT_STR] = account_name   # add account column from filename

    with get_connection() as conn:
        for _, row in df.iterrows():
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO transactions
                    (date, place, expense, income, credit_card, account, category, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row["date"], row["place"], row["expense"], row["income"],
                    row["credit_card"], row[ACCOUNT_STR], row["category"], row["source_file"]
                ))
            except Exception as e:
                print(f"Error inserting row: {e}")
        conn.commit()

def bootstrap_database(data_folder, config):
    create_transactions_table()
    for file in os.listdir(data_folder):
        if file.endswith(".csv"):
            update_database("add", os.path.join(data_folder, file), config)

def get_dataframe_from_database():
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
    return df

def update_transaction_category_db(transaction_id, new_category):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE transactions
            SET category = ?
            WHERE id = ?
        """, (new_category, transaction_id))
        
        if cursor.rowcount == 0:
            print(f"No transaction found with ID {transaction_id}")
        else:
            print(f"Updated transaction ID {transaction_id} to category '{new_category}'")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error while updating category: {e}")
    finally:
        conn.close()