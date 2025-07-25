# IBKR Price Update Service

This document describes the IBKR (Interactive Brokers) price update functionality in the HE Alerts system.

## Overview

The IBKR price update service fetches real-time market prices for all active stocks in the database twice daily:
- **AM Session**: 10:45 ET (configured in settings)
- **PM Session**: 14:30 ET (configured in settings)

## Components

### 1. Contract Resolver (`app/services/ibkr/contract_resolver.py`)
- Classifies assets (stocks, ETFs, crypto, futures, etc.)
- Creates IBKR contract objects
- Handles special cases like crypto stocks (MSTR, COIN) vs pure crypto (BTC, ETH)

### 2. Price Fetcher (`app/services/ibkr/price_fetcher.py`)
- Connects to IBKR Gateway/TWS
- Resolves and caches contract details
- Fetches snapshot prices
- Checks for buy/sell alerts

### 3. Price Update Scheduler (`app/services/scheduler/price_updater.py`)
- Runs scheduled price updates
- Processes triggered alerts
- Integrates with the alert service

### 4. Alert Service (`app/services/database/alert_service.py`)
- Logs price alerts to database
- Tracks alert history
- Provides alert queries

## Configuration

Set these environment variables in `.env`:

```env
# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497          # 7497 for paper trading, 7496 for live
IBKR_CLIENT_ID=1
IBKR_PAPER_TRADING=true

# Schedule times (ET)
MORNING_PRICE_TIME=10:45
AFTERNOON_PRICE_TIME=14:30
```

## Prerequisites

1. **IBKR Gateway or TWS** must be running
2. **API connections** must be enabled in IBKR settings
3. **Market data subscriptions** for the assets you're tracking

## Usage

### Manual Price Update

```bash
# Run AM price update
python test_price_update.py AM

# Run PM price update  
python test_price_update.py PM

# Get single ticker price
python test_price_update.py ticker AAPL

# Check which stocks need prices
python test_price_update.py check
```

### API Endpoints

```bash
# Trigger price update via API
POST /api/v1/prices/update/AM
POST /api/v1/prices/update/PM

# Get single ticker price
GET /api/v1/prices/ticker/AAPL

# Get recent alerts
GET /api/v1/prices/alerts/recent?limit=50

# Get alerts for specific ticker
GET /api/v1/prices/alerts/ticker/AAPL

# Get price update status
GET /api/v1/prices/status
```

### Running with Schedulers

```bash
# Start server with schedulers enabled
python -m app.main_with_scheduler
```

## Alert Logic

Alerts are triggered when:
- **BUY Alert**: Current price <= buy_trade threshold
- **SELL Alert**: Current price >= sell_trade threshold

Alerts are logged to the `alert_logs` table with:
- Ticker
- Alert type (BUY/SELL)
- Current price
- Threshold price
- Sentiment
- Timestamp

## Database Schema

### Stock Price Fields
- `am_price`: Morning session price
- `pm_price`: Afternoon session price  
- `last_price_update`: Timestamp of last update
- `ibkr_contract`: Cached contract details (JSON)
- `ibkr_contract_resolved`: Boolean flag

### Alert Log Fields
- `ticker`: Stock ticker
- `alert_type`: BUY or SELL
- `price`: Current market price
- `threshold`: Alert threshold price
- `sentiment`: Stock sentiment
- `created_at`: Alert timestamp

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Ensure IBKR Gateway/TWS is running
   - Check port settings (7497 for paper, 7496 for live)
   - Verify API connections are enabled

2. **No Price Data**
   - Check market data subscriptions
   - Verify market hours
   - Check contract resolution in logs

3. **Contract Not Found**
   - Some tickers may need manual mapping
   - Check exchange settings
   - Verify ticker symbols

### Logging

Logs are written to:
- Console output (structured logging)
- Database alert_logs table
- Application logs

## Testing

```bash
# Create alert_logs table
python create_alert_logs_table.py

# Test price fetching
python test_price_update.py AM

# Check API endpoints
curl http://localhost:8000/api/v1/prices/status
```

## Performance Considerations

- Price updates are rate-limited (0.5s delay between tickers)
- Contract details are cached after first resolution
- Snapshot data is used (not streaming) to minimize connections
- Database commits are batched for efficiency