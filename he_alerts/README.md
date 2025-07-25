# HE Alerts

Automated stock alert system that fetches daily financial emails, extracts trading signals using AI, and generates price-based alerts through IBKR integration.

## 🏗️ System Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        Gmail[Gmail API]
        IBKR[IBKR TWS/Gateway]
    end

    subgraph "Processing Pipeline"
        Fetch[Email Fetcher]
        Extract[Data Extractor<br/>OCR + HTML Parser]
        DB[(PostgreSQL)]
        Price[Price Fetcher]
        Alert[Alert Generator]
    end

    subgraph "Outputs"
        Email[Alert Emails]
        CSV[Validation CSV]
    end

    Gmail -->|Fetch Daily/Crypto| Fetch
    Fetch --> Extract
    Extract -->|Delete & Insert| DB
    IBKR -->|Real-time Prices| Price
    Price -->|Update| DB
    DB --> Alert
    Alert --> Email
    Extract --> CSV
```

## ✨ Features

- **Email Processing**: Automated extraction from Daily and Crypto financial newsletters
- **AI-Powered OCR**: Uses Mistral AI's Pixtral model to extract data from embedded images
- **Smart Data Management**: Delete-before-insert strategy ensures no stale data
- **IBKR Integration**: Real-time price fetching via Interactive Brokers API
- **Alert System**: Sentiment-based buy/sell alerts with configurable thresholds
- **Validation Workflow**: Review extracted data before database updates
- **FastAPI REST API**: Web interface for monitoring and manual operations
- **Automated Scheduling**: AM/PM trading session automation

## 📧 Email Types Processed

1. **Daily Signals** (`daily`): Market Range signals with buy/sell thresholds
2. **Crypto Signals** (`digitalassets`): Cryptocurrency and crypto stock levels from embedded images

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon.tech recommended)
- Gmail API credentials
- Mistral AI API key
- Interactive Brokers TWS/Gateway
- SMTP server for alerts

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stockalert.git
cd stockalert/he_alerts
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize the database:
```bash
python scripts/init_db.py
```

## 🔧 Configuration

Key environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Gmail API
GMAIL_CREDENTIALS_PATH=/path/to/credentials.json

# AI Processing
MISTRAL_API_KEY=your-mistral-api-key

# IBKR Connection
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Email Alerts
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=alerts@yourdomain.com
ALERT_TO_EMAILS=["recipient1@example.com", "recipient2@example.com"]
```

## 📊 Alert Rules

The system uses sentiment-based alert generation:

### BULLISH Sentiment
- **BUY Alert**: When current_price ≤ buy_trade
- **SELL Alert**: When current_price ≥ sell_trade

### BEARISH Sentiment  
- **BUY Alert**: When current_price ≥ buy_trade
- **SELL Alert**: When current_price ≤ sell_trade

### NEUTRAL Sentiment
- Same as BULLISH rules

## 🏃‍♂️ Running the System

### 1. Validation Workflow (Recommended)
First validate what will be extracted:
```bash
python he_alerts/validate_emails.py
# Review the generated CSV file
# Then if everything looks good:
python he_alerts/fetch_latest_emails.py
```

### 2. Complete Alert Workflow
Run the full pipeline:
```bash
python he_alerts/alert_workflow.py
```

Options:
- `--session [AM|PM]`: Specify trading session
- `--skip-price-fetch`: Use existing prices
- `--no-email`: Generate alerts without sending
- `--test-mode`: Send to test recipients only

### 3. Automated Scheduler (Production)
For production deployment with market holiday awareness:
```bash
python he_alerts/automated_scheduler.py
```

This runs automatically on market days only:
- **Email Extraction**: 9:00 AM EST
  - First market day of week: All 4 types (daily, crypto, etfs, ideas)
  - Other market days: 2 types (daily, crypto)
- **Morning Alerts**: 10:45 AM EST
- **Afternoon Alerts**: 2:30 PM EST

The scheduler automatically skips US market holidays.

## 📁 Project Structure

```
he_alerts/
├── app/
│   ├── api/                # FastAPI routes
│   ├── core/               # Configuration, database
│   ├── models/             # SQLAlchemy models (single stocks table)
│   ├── schemas/            # Pydantic schemas
│   └── services/           # Business logic
│       ├── alert_generator.py
│       ├── email_processor.py
│       ├── email_sender.py
│       └── ibkr/
│           ├── contract_resolver.py
│           └── price_fetcher.py
├── scripts/
│   ├── init_db.py          # Database initialization
│   └── diagnostics/        # Check scripts
├── docs/                   # Documentation
│   ├── AUTOMATED_SCHEDULER.md
│   ├── FLOW_DIAGRAM.md
│   └── SYSTEM_ARCHITECTURE.md
├── alert_workflow.py       # Main workflow orchestrator
├── automated_scheduler.py  # Production scheduler with holidays
├── fetch_latest_emails.py  # Email extraction
└── validate_emails.py      # Validation without DB update
```

## 🗄️ Database Schema

Single table design for simplicity:

```sql
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    sentiment VARCHAR(20),
    buy_trade DECIMAL(10, 2),
    sell_trade DECIMAL(10, 2),
    current_price DECIMAL(10, 2),
    price_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, category)
);
```

## 🔍 Key Implementation Details

### Email Processing
- **Delete-before-insert**: Each category is cleared before new data insertion
- **OCR for Crypto**: Extracts data from specific image indices (6 & 14)
- **HTML Parsing**: Daily emails use BeautifulSoup for table extraction

### Price Updates
- **Async IBKR**: Uses ib_async for non-blocking price fetches
- **Smart Contract Resolution**: Maps tickers to appropriate IBKR contracts
- **Batch Processing**: Updates multiple stocks efficiently

### Alert Generation
- **In-memory Tracking**: Prevents duplicate alerts within session
- **Formatted Emails**: HTML emails with clear buy/sell recommendations
- **Test Mode**: Safely test alerts before production deployment

## 🚀 Deployment

### Replit Deployment

1. Create a new Repl from GitHub
2. Set up PostgreSQL database
3. Configure Secrets (environment variables)
4. Set up Always On for scheduled execution

### Local Development
```bash
# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the scheduler
python he_alerts/start_server.py
```

## 📈 Monitoring

- **Health Check**: `GET /health` endpoint
- **Logs**: Structured logging with timestamps
- **CSV Exports**: Validation reports for manual review
- **Email Notifications**: Alert delivery confirmation

## 🐛 Troubleshooting

### Common Issues

1. **OCR Extraction Failures**
   - Check Mistral API key
   - Verify image URLs are accessible
   - Review extraction logs

2. **IBKR Connection Issues**
   - Ensure TWS/Gateway is running
   - Check port configuration
   - Verify API permissions

3. **Email Delivery Failures**
   - Verify SMTP credentials
   - Check spam folders
   - Review SMTP logs

## 📝 License

This project is private and proprietary.

## 🤝 Support

For issues and questions, please contact the development team.