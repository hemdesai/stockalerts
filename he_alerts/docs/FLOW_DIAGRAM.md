# HE Alerts System Flow Diagrams

## Complete System Flow

```mermaid
flowchart TB
    Start([Start]) --> Schedule{Scheduled<br/>or Manual?}
    
    Schedule -->|Scheduled| AM[AM Session<br/>9:00 AM EST]
    Schedule -->|Scheduled| PM[PM Session<br/>3:30 PM EST]
    Schedule -->|Manual| Manual[Manual Trigger]
    
    AM --> Workflow
    PM --> Workflow
    Manual --> Workflow
    
    subgraph Workflow[Alert Workflow]
        FetchEmails[1. Fetch Emails<br/>from Gmail]
        ProcessEmails[2. Process Emails]
        UpdateDB[3. Update Database]
        FetchPrices[4. Fetch IBKR Prices]
        GenerateAlerts[5. Generate Alerts]
        SendAlerts[6. Send Alert Emails]
    end
    
    FetchEmails --> ProcessEmails
    ProcessEmails --> UpdateDB
    UpdateDB --> FetchPrices
    FetchPrices --> GenerateAlerts
    GenerateAlerts --> SendAlerts
    
    SendAlerts --> End([End])
```

## Email Processing Detail

```mermaid
flowchart LR
    subgraph Gmail
        Daily[Daily Email]
        Crypto[Crypto Email]
    end
    
    subgraph Processing
        Classify[Classify by<br/>Subject]
        DailyProc[Daily Processor]
        CryptoProc[Crypto Processor]
        
        subgraph DailyExtract[Daily Extraction]
            HTML[HTML Parser]
            Table[Extract Table]
        end
        
        subgraph CryptoExtract[Crypto Extraction]
            Images[Download Images]
            OCR[OCR with Mistral]
            Parse[Parse Tables]
        end
    end
    
    subgraph Database
        Delete[Delete Category<br/>Stocks]
        Insert[Insert New<br/>Stocks]
    end
    
    Daily --> Classify
    Crypto --> Classify
    
    Classify -->|daily| DailyProc
    Classify -->|crypto| CryptoProc
    
    DailyProc --> HTML
    HTML --> Table
    
    CryptoProc --> Images
    Images -->|Image 6| OCR
    Images -->|Image 14| OCR
    OCR --> Parse
    
    Table --> Delete
    Parse --> Delete
    Delete --> Insert
```

## Alert Generation Logic

```mermaid
flowchart TD
    Stock[Stock Record] --> Check{Has Current<br/>Price?}
    Check -->|No| Skip[Skip Stock]
    Check -->|Yes| Sentiment{Sentiment?}
    
    Sentiment -->|BULLISH| BullRules[Bullish Rules]
    Sentiment -->|BEARISH| BearRules[Bearish Rules]  
    Sentiment -->|NEUTRAL| NeutRules[Neutral Rules]
    
    BullRules --> BullBuy{Price ≤<br/>Buy Trade?}
    BullRules --> BullSell{Price ≥<br/>Sell Trade?}
    
    BearRules --> BearBuy{Price ≥<br/>Buy Trade?}
    BearRules --> BearSell{Price ≤<br/>Sell Trade?}
    
    NeutRules --> NeutBuy{Price ≤<br/>Buy Trade?}
    NeutRules --> NeutSell{Price ≥<br/>Sell Trade?}
    
    BullBuy -->|Yes| BuyAlert[Generate<br/>BUY Alert]
    BullSell -->|Yes| SellAlert[Generate<br/>SELL Alert]
    
    BearBuy -->|Yes| BuyAlert
    BearSell -->|Yes| SellAlert
    
    NeutBuy -->|Yes| BuyAlert
    NeutSell -->|Yes| SellAlert
    
    BuyAlert --> Email[Send Email]
    SellAlert --> Email
```

## Validation Workflow

```mermaid
flowchart LR
    Start([Start Validation]) --> Fetch[Fetch Latest<br/>Emails]
    Fetch --> Extract[Extract Data<br/>WITHOUT DB Update]
    Extract --> Compare[Compare with<br/>Current DB]
    
    Compare --> Report{Generate<br/>Report}
    
    Report --> CSV[Export CSV]
    Report --> Console[Console Summary]
    
    CSV --> Review{Manual<br/>Review}
    Console --> Review
    
    Review -->|Approved| Update[Run fetch_latest_emails.py<br/>to Update DB]
    Review -->|Issues Found| Fix[Fix Issues<br/>and Re-validate]
    
    Fix --> Start
    Update --> Done([Done])
```

## Database Operations

```mermaid
sequenceDiagram
    participant Email as Email Processor
    participant Service as Stock Service
    participant DB as PostgreSQL
    
    Email->>Service: upsert_stocks_from_email(stocks, category)
    
    Note over Service: Begin Transaction
    
    Service->>DB: DELETE FROM stocks WHERE category = ?
    DB-->>Service: Rows deleted
    
    loop For each stock
        Service->>DB: INSERT INTO stocks (ticker, category, ...)
        DB-->>Service: Stock created
    end
    
    Note over Service: Commit Transaction
    
    Service-->>Email: Stocks updated
```

## IBKR Price Update Flow

```mermaid
flowchart TB
    Start([Start Price Update]) --> GetStocks[Get Stocks<br/>Needing Prices]
    
    GetStocks --> Connect[Connect to<br/>IBKR TWS/Gateway]
    
    Connect --> Loop{For Each<br/>Stock}
    
    Loop --> Resolve[Resolve Contract<br/>STK/CRYPTO/CASH]
    Resolve --> Request[Request<br/>Market Data]
    Request --> Wait[Wait for<br/>Price Tick]
    
    Wait --> Success{Price<br/>Received?}
    
    Success -->|Yes| Update[Update DB<br/>with Price]
    Success -->|No| Log[Log Error]
    
    Update --> More{More<br/>Stocks?}
    Log --> More
    
    More -->|Yes| Loop
    More -->|No| Disconnect[Disconnect<br/>from IBKR]
    
    Disconnect --> End([End])
```

## Error Handling

```mermaid
flowchart TD
    Operation[Any Operation] --> Try{Try<br/>Operation}
    
    Try -->|Success| Continue[Continue<br/>Workflow]
    Try -->|Error| Type{Error<br/>Type?}
    
    Type -->|Gmail Auth| GmailErr[Log & Exit<br/>Check Credentials]
    Type -->|OCR Failure| OCRErr[Log & Continue<br/>Partial Data]
    Type -->|IBKR Connect| IBKRErr[Log & Skip<br/>Price Update]
    Type -->|DB Error| DBErr[Rollback<br/>Retry Once]
    Type -->|SMTP Error| SMTPErr[Log Alerts<br/>To File]
    
    DBErr --> Retry{Retry<br/>Success?}
    Retry -->|Yes| Continue
    Retry -->|No| Fatal[Log & Exit]
```

## Deployment Architecture

```mermaid
graph TB
    subgraph Replit["Replit Environment"]
        App[FastAPI App<br/>Port 8000]
        Scheduler[APScheduler]
        Secrets[Environment<br/>Secrets]
    end
    
    subgraph External["External Services"]
        Neon[(Neon<br/>PostgreSQL)]
        Gmail[Gmail API]
        IBKR[IBKR Gateway]
        Mistral[Mistral AI]
        SMTP[SMTP Server]
    end
    
    subgraph Schedule["Scheduled Tasks"]
        Morning[9:00 AM EST]
        Afternoon[3:30 PM EST]
    end
    
    Morning --> Scheduler
    Afternoon --> Scheduler
    
    Scheduler --> App
    
    App <--> Neon
    App <--> Gmail
    App <--> IBKR
    App <--> Mistral
    App <--> SMTP
    
    Secrets --> App
```