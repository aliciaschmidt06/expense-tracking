#!/bin/bash

# Define paths
DATA_DIR="data"
CONFIG_FILE="configs/config.yaml"
CONTACTS_FILE="configs/contacts.yaml"

# Create data directory if it doesn't exist
if [ ! -d "$DATA_DIR" ]; then
  echo "Creating $DATA_DIR directory..."
  mkdir -p "$DATA_DIR"
fi

# Create config.yaml with default contents if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Creating default config.yaml..."
  cat > "$CONFIG_FILE" <<EOF
income:
  keywords:
  - payroll
  - cashback
spending_categories:
  business:
    keywords:
    - staples
    target_range:
    - 0
    - 0
  dining:
    keywords:
    - restaurant
    - tavern
    - brewing
    target_range:
    - 0.0
    - 0.05
  fixed:
    keywords:
    - bell
    - shell
    - loblaws
    - superstore
    target_range:
    - 0.0
    - 0.5
  guilt_free:
    keywords:
    - amazon
    - pub
    - sephora
    - liquor
    - bakery
    - indigo
    target_range:
    - 0.0
    - 0.2
  investments:
    keywords:
    - retirement
    - stocks
    - bonds
    target_range:
    - 0.1
    - 0.2
  vacation:
    keywords:
    - airbnb
    - hostel
    target_range:
    - 0
    - 0.05
ignore:
  - annual bank fee
EOF
fi

# Create contacts.yaml with default contents if it doesn't exist
if [ ! -f "$CONTACTS_FILE" ]; then
  echo "Creating default contacts.yaml..."
  cat > "$CONTACTS_FILE" <<EOF
contacts:
  - name: employer
    keyword: Some Place
EOF
fi

# Create a dummy database file if it doesnt exist
if [ ! -f "expenses.db" ]; then
  echo "Creating empty expenses.db file..."
  touch expenses.db
fi

# Start Docker Compose
echo "Starting Docker Compose..."
docker compose up --build