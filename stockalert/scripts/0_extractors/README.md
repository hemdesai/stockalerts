# Email Extractors

This directory contains email extractors that process financial data from Gmail emails.

## Extraction Schedule

The extractors follow these frequency rules:

### Daily Extractors
- **crypto_extractor.py**: Extracts crypto data from "FW: CRYPTO QUANT" emails (daily)
- **daily_extractor.py**: Extracts daily trading signals (daily)

### Weekly Extractors (Monday unless public holiday)
- **etf_extractor.py**: Extracts ETF data from "ETF Pro Plus - Levels" emails (weekly)
- **ideas_extractor.py**: Extracts investment ideas from "FW: Investing Ideas Newsletter:" emails (weekly)

## How It Works

1. Each extractor searches Gmail for emails with specific subjects
2. Extracts attachments (images or HTML content)
3. Processes the data using Mistral OCR for images
4. Saves the extracted data to CSV files in the data directory

## Email Search Logic

- **Daily extractors**: Search for emails from today, with fallback to yesterday
- **Weekly extractors**: Search for emails from the last 7 days

## Fallback Mechanism

All extractors support fallback to local files if email extraction fails:
- crypto_extractor: Falls back to crypto1.png and crypto2.png
- ideas_extractor: Falls back to ideas.png
- etf_extractor: No local fallback (email only)
- daily_extractor: No local fallback (email only)