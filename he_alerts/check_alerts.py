import pandas as pd

df = pd.read_csv('stocks_updated_20250725_081637.csv')

print("Checking for potential alerts...")
print("="*60)

alert_count = 0

# Check for potential alerts
for _, stock in df.iterrows():
    if pd.notna(stock['am_price']) and pd.notna(stock['buy_trade']) and pd.notna(stock['sell_trade']):
        sentiment = stock['sentiment'].lower() if pd.notna(stock['sentiment']) else ''
        if sentiment == 'bullish':
            if stock['am_price'] <= stock['buy_trade']:
                print(f"BUY ALERT: {stock['ticker']} at ${stock['am_price']:.2f} <= ${stock['buy_trade']:.2f}")
                alert_count += 1
            elif stock['am_price'] >= stock['sell_trade']:
                print(f"SELL ALERT: {stock['ticker']} at ${stock['am_price']:.2f} >= ${stock['sell_trade']:.2f}")
                alert_count += 1
        elif sentiment == 'bearish':
            if stock['am_price'] >= stock['sell_trade']:
                print(f"SHORT ALERT: {stock['ticker']} at ${stock['am_price']:.2f} >= ${stock['sell_trade']:.2f}")
                alert_count += 1
            elif stock['am_price'] <= stock['buy_trade']:
                print(f"COVER ALERT: {stock['ticker']} at ${stock['am_price']:.2f} <= ${stock['buy_trade']:.2f}")
                alert_count += 1

print(f"\nTotal potential alerts: {alert_count}")

# Show stocks with prices
stocks_with_prices = df[pd.notna(df['am_price'])]
print(f"\nStocks with AM prices: {len(stocks_with_prices)}")
for _, stock in stocks_with_prices.iterrows():
    print(f"  {stock['ticker']}: ${stock['am_price']:.2f} (Buy: ${stock['buy_trade']:.2f}, Sell: ${stock['sell_trade']:.2f})")