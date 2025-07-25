# HE Alerts System Architecture

## Overview

The HE Alerts system is an automated stock alert system that:
1. Fetches daily emails from Gmail (Daily and Crypto)
2. Extracts stock data using OCR for embedded images
3. Updates PostgreSQL database with latest prices and sentiment
4. Fetches real-time prices from Interactive Brokers (IBKR)
5. Generates alerts based on price thresholds and sentiment rules
6. Sends email notifications for triggered alerts

## System Flow Diagram

```mermaid
graph TB
    subgraph "Email Sources"
        Gmail[Gmail API]
        Daily[Daily Email]
        Crypto[Crypto Email]
    end

    subgraph "Email Processing"
        Fetch[Email Fetcher]
        Classify[Email Classifier]
        Extract[Data Extractor]
        OCR[OCR Service<br/>Mistral AI]
    end

    subgraph "Data Storage"
        DB[(PostgreSQL<br/>Neon.tech)]
        Stocks[Stocks Table]
    end

    subgraph "Price Updates"
        IBKR[IBKR API]
        PriceFetch[Price Fetcher]
        Contract[Contract Resolver]
    end

    subgraph "Alert Generation"
        AlertGen[Alert Generator]
        Rules[Alert Rules]
    end

    subgraph "Notifications"
        SMTP[SMTP Service]
        Email[Alert Emails]
    end

    Gmail --> Fetch
    Fetch --> Classify
    Classify --> |Daily| Daily
    Classify --> |Crypto| Crypto
    
    Daily --> Extract
    Crypto --> Extract
    Extract --> OCR
    OCR --> |Extracted Data| DB
    
    DB --> |Delete Old| Stocks
    DB --> |Insert New| Stocks
    
    Stocks --> PriceFetch
    IBKR --> Contract
    Contract --> PriceFetch
    PriceFetch --> |Update Prices| Stocks
    
    Stocks --> AlertGen
    Rules --> AlertGen
    AlertGen --> |Triggered Alerts| SMTP
    SMTP --> Email
```

## Component Details

### 1. Email Processing Pipeline

```mermaid
sequenceDiagram
    participant Gmail
    participant Fetcher
    participant Processor
    participant Extractor
    participant OCR
    participant DB

    Gmail->>Fetcher: Fetch recent emails (72h)
    Fetcher->>Processor: Classify by type
    Processor->>Extractor: Process Daily email
    Processor->>Extractor: Process Crypto email
    
    Note over Extractor: Daily uses HTML parsing
    Note over Extractor: Crypto uses image OCR
    
    Extractor->>OCR: Extract from images (Crypto)
    OCR-->>Extractor: Parsed data
    
    Extractor->>DB: Delete category stocks
    Extractor->>DB: Insert new stocks
```

### 2. Alert Generation Workflow

```mermaid
flowchart LR
    subgraph "Price Check"
        CP[Current Price]
        BT[Buy Threshold]
        ST[Sell Threshold]
    end
    
    subgraph "Sentiment Rules"
        Bull[BULLISH:<br/>Buy if price ≤ buy_trade<br/>Sell if price ≥ sell_trade]
        Bear[BEARISH:<br/>Buy if price ≥ buy_trade<br/>Sell if price ≤ sell_trade]
        Neut[NEUTRAL:<br/>Buy if price ≤ buy_trade<br/>Sell if price ≥ sell_trade]
    end
    
    subgraph "Alert Types"
        BA[BUY Alert]
        SA[SELL Alert]
    end
    
    CP --> Bull
    CP --> Bear
    CP --> Neut
    
    Bull --> |Condition Met| BA
    Bull --> |Condition Met| SA
    Bear --> |Condition Met| BA
    Bear --> |Condition Met| SA
    Neut --> |Condition Met| BA
    Neut --> |Condition Met| SA
```

## Database Schema

```sql
-- Single table design for simplicity
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

## Key Implementation Details

### Email Processing
- **Delete-before-insert strategy**: Ensures no stale data remains
- **Category-based deletion**: Each email type clears its category before inserting
- **OCR for images**: Crypto emails contain embedded images requiring OCR

### Price Updates
- **IBKR Integration**: Uses ib_async for real-time price fetching
- **Contract Resolution**: Maps stock tickers to IBKR contracts
- **Batch Processing**: Updates multiple stocks efficiently

### Alert Rules
- **Sentiment-based**: Different rules for BULLISH, BEARISH, and NEUTRAL
- **Price thresholds**: Compares current price against buy/sell trades
- **No duplicate alerts**: Checks recent alert history (in-memory)

### Email Categories
1. **daily**: Stocks from daily market email
2. **digitalassets**: Crypto and crypto stocks (BTC, ETH, MSTR, etc.)
3. **etfs**: ETF positions
4. **ideas**: Trading ideas

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        App[FastAPI App]
        Worker[Background Worker]
        PG[(PostgreSQL)]
        
        subgraph "External Services"
            GM[Gmail API]
            IB[IBKR TWS/Gateway]
            AI[Mistral AI API]
            SM[SMTP Server]
        end
    end
    
    subgraph "Scheduled Tasks"
        AM[AM Session<br/>9:00 AM EST]
        PM[PM Session<br/>3:30 PM EST]
    end
    
    AM --> Worker
    PM --> Worker
    Worker --> App
    App --> PG
    App --> GM
    App --> IB
    App --> AI
    App --> SM
```

## Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Gmail
GMAIL_CREDENTIALS_PATH=/path/to/credentials.json

# IBKR
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Mistral AI
MISTRAL_API_KEY=your-api-key

# SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email
SMTP_PASSWORD=your-app-password

# Alerts
ALERT_FROM_EMAIL=alerts@example.com
ALERT_TO_EMAILS=["recipient@example.com"]
```

## Operational Workflows

### 1. Manual Validation Workflow
```bash
# Validate email extraction without updating DB
python he_alerts/validate_emails.py

# Review CSV output
# Then update database if validated
python he_alerts/fetch_latest_emails.py
```

### 2. Complete Alert Workflow
```bash
# Run complete workflow (fetch, update, alert)
python he_alerts/alert_workflow.py

# Or run with options
python he_alerts/alert_workflow.py --skip-price-fetch --test-mode
```

### 3. Scheduled Execution
```bash
# Start server with scheduler
python he_alerts/start_server.py

# Or run scheduled alerts directly
python he_alerts/scheduled_alerts.py
```

## Error Handling

- **Email fetch failures**: Logged, continues with available emails
- **OCR failures**: Falls back to partial extraction
- **IBKR connection issues**: Skips price update, uses existing prices
- **Database errors**: Transaction rollback, operation retry
- **SMTP failures**: Logs alert content for manual review

## Monitoring

- **Logs**: Structured logging with correlation IDs
- **Health endpoint**: `/health` for uptime monitoring
- **Metrics**: Stock count, alert count, processing time
- **Email validation**: CSV export for manual review before updates