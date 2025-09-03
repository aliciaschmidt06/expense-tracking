# Expense Tracking

A tool to help visualize personal finance and track/categorize my spending.

## Dependencies 

- docker & docker compose 
- python (3.10+)

## Quick Start

1. clone repo
2. cd into expense-tracking/
3. ./run.sh
   
## Manual Build & Run 

1. clone the repo
2. cd into expense-tracking/
3. docker build -t expense-tracker .
4. docker run -p 8501:8501 expense-tracker

## Usage 

1. Download/export account transactions for any number of accounts from banking website
2. make sure this web service is available at localhost:8501
3. upload your csv files

## Features
- Spending Plan 
- Subscriptions & Re-Ocurring Charges
- History Analysis & Search 
- Money Owed Management


## Manual Docker Run

1. cd into directory where your configs & data is
2.

```docker run -d \
  --name expense-tracker \
  --restart unless-stopped \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.configs/config.yaml:/app/config.yaml \
  -v $(pwd)/.configs/contacts.yaml:/contacts.yaml \
  -v $(pwd)/expenses.db:/expenses.db \
  -e PYTHONUNBUFFERED=1 \
  expense-tracker \
  streamlit run app.py --server.port=8501 --server.enableCORS=false expense-tracker:latest```