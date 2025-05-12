# Expense Tracking

A tool to help visualize personal finance and track/categorize my spending.

## Dependencies 

- docker & docker compose 
- python (3.10+)

## Manual Build & Run 

1. clone the repo
2. cd into expense-tracking/
3. docker build -t expense-tracker .
4. docker run -p 8501:8501 expense-tracker

## Deployment

1. clone repo
2. cd into expense-tracking/
3. ./run.sh

## Usage 

1. Download/export account transactions for any number of accounts from banking website
2. make sure this web service is available at localhost:8501
3. upload your csv files

## Features
- Spending Plan 
- Subscriptions & Re-Ocurring Charges
- History Analysis & Search 
- Money Owed Management
