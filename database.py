import sqlite3
import pandas as pd
import os
import yaml

DB_FILE = 'expenses.db'
CONFIG_FILE = 'config.yaml'

def initialize_database():
    conn = sqlite3.connect(DB_FILE)
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
        UNIQUE(date, place, expense, income, credit_card, account)
    )
    ''')
    conn.commit()
    conn.close()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as file:
            yaml.dump({'spending_categories': {}}, file)
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
    return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        yaml.dump(config, file)

def categorize_transaction(place, config):
    place_lower = place.lower()
    matched_category = None
    
    for category, settings in config.get('spending_categories', {}).items():
        keywords = settings.get("keywords", [])
        
        for keyword in keywords:
            if keyword.lower() in place_lower:
                matched_category = category
                return category
    
    return 'unknown'

def load_data_from_csv(selected_files=None):
    data_folder = './data/'
    data_frames = []
    
    for file in os.listdir(data_folder):
        if file.endswith('.csv'):
            if selected_files and file not in selected_files:
                continue

            account_name = file.replace('.csv', '') 
            df = pd.read_csv(
                os.path.join(data_folder, file), 
                header=None, 
                names=["Date", "Place", "Expense", "Income", "CreditCard"],
                dtype={"Expense": float, "Income": float}
            )

            df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors='coerce')
            df.fillna({"Expense": 0, "Income": 0, "CreditCard": ""}, inplace=True)
            df["Account"] = account_name

            data_frames.append(df)

    if data_frames:
        df = pd.concat(data_frames, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["Date", "Place", "Expense", "Income", "CreditCard", "Account"])
    return df


def update_database_with_new_data(selected_files=None, config=None):
    if config is None:
        config = load_config()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    df = load_data_from_csv(selected_files)

    for _, row in df.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d') if pd.notnull(row['Date']) else None
        category = categorize_transaction(row['Place'], config)

        try:
            cursor.execute('''
            INSERT INTO transactions (date, place, expense, income, credit_card, account, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (date_str, row['Place'], row['Expense'], row['Income'], row['CreditCard'], row['Account'], category))
        except sqlite3.IntegrityError:
            continue

    conn.commit()
    conn.close()

def update_transaction_category_db(transaction, new_category):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE transactions
        SET category = ?
        WHERE id = ?
    """, (new_category.strip(), transaction["id"]))

    rows_updated = cursor.rowcount
    print(f"[DEBUG] Rows updated: {rows_updated}")
    
    conn.commit()
    conn.close()
    return True


def get_data_from_database():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql('SELECT * FROM transactions', conn, parse_dates=['date'])
    conn.close()
    df.rename(columns={'date': 'Date', 'place': 'Place', 'expense': 'Expense', 'income': 'Income', 'credit_card': 'CreditCard', 'account': 'Account', 'category': 'Category'}, inplace=True)
    return df

