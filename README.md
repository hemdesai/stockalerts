# StockAlert

A comprehensive stock and digital assets tracking and alerting system that extracts data from emails, processes it, and provides actionable trading alerts.

## Features

- **Gmail Extractor**: Automatically extracts financial data from emails with specific subjects
  - Processes "RISK RANGE", "CRYPTO QUANT", and other financial data emails
  - Uses Mistral OCR for image processing
  - Handles stocks, ETFs, cryptocurrencies, and daily trading signals

- **Data Validation**: Ensures data integrity and accuracy
  - Maps ticker symbols to standard formats (e.g., BTC → BTC-USD)
  - Validates price data against historical records

- **Database Management**: SQLite-based storage for financial data
  - Maintains historical records
  - Optimized queries for alert generation

- **Automated Scheduling**:
  - Daily/weekly updates depending on asset type
  - CSV data generation at ~9:00 AM ET
  - Database import at 10:55 AM ET
  - Alerts at 11:05 AM and 2:35 PM ET

- **Email Notifications**:
  - CSV update notifications with data summaries
  - Trading alerts with buy/sell recommendations
  - Profit potential calculations

- **Dashboard**: Streamlit-based visualization of financial data

## Project Structure

```
cursor_stockalert/
├── .env                      # Single consolidated environment file (root)
├── .gitignore                # Central ignore file (covers logs, venv, data, etc.)
├── logs/                     # All application logs centralized here
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── stockalert/               # Main application package
│   ├── credentials/          # Service and app credentials (not in version control)
│   ├── data/                 # SQLite DB and data files (gitignored)
│   ├── scripts/              # All core scripts and modules
│   │   ├── alert_system.py   # Alert generation logic
│   │   ├── 4_prices_ibkr.py  # IBKR async price updater
│   │   ├── 5_send_alerts.py  # Alert sending script
│   │   ├── ...               # Other scripts (see folder)
│   ├── utils/                # Shared utilities (env_loader, etc.)
│   └── ...                   # Other app modules
└── venv/ or .venv/           # Python virtual environment (gitignored)
```

- **All logs are written to `logs/` at the repo root.**
- **Only one `.env` file at the root is used for all scripts.**
- **No duplicate or legacy folders; everything is consolidated for clarity.**
- **All caches and pyc files are gitignored and excluded from source control.**

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/hemdesai/stockalert.git
   cd stockalert
   ```

2. Install dependencies:
   ```
   pip install -r stockalert/requirements.txt
   ```

3. Set up environment variables:
   ```
   cp stockalert/env_template.txt stockalert/.env
   ```
   Edit the `.env` file with your specific configuration.

4. **Ensure IBKR Gateway is running:**
    - Before running any scripts that fetch live prices (e.g., 4_prices_ibkr.py or 5_send_alerts.py), make sure the IBKR Gateway is open and accessible on your machine. Without this, price fetching will fail.

5. Run the dashboard:
    ```
    cd stockalert
    streamlit run dashboard.py
    ```

6. Set up scheduled tasks:
   ```
   python -m stockalert.scripts.data_import_scheduler --run-scheduler
   ```

## Environment Variables

The following environment variables need to be set in the `.env` file:

- `MISTRAL_API_KEY`: API key for Mistral OCR
- `EMAIL_SENDER`: Gmail address for sending alerts
- `EMAIL_PASSWORD`: App password for Gmail
- `EMAIL_RECIPIENT`: Email address to receive alerts
- `DATA_DIR`: Directory for data storage (default: "data")
- `DB_PATH`: Path to SQLite database (default: "data/stocks.db")
- `SCHEDULER_ENABLED`: Enable/disable scheduler (default: "true")
- `CSV_IMPORT_TIME`: Time to import CSV data (default: "08:45")
- `DB_IMPORT_TIME`: Time to import to database (default: "10:55")
- `ALERT_TIMES`: Times to send alerts (default: "11:05,14:35")

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Mistral AI](https://mistral.ai/) for OCR capabilities
- [Streamlit](https://streamlit.io/) for dashboard visualization