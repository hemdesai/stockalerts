import pandas as pd

df = pd.read_csv('stocks_updated_20250725_081637.csv')

# Show all digital assets
crypto_stocks = df[df['category'] == 'digitalassets'].sort_values('ticker')
print('CURRENT DIGITAL ASSETS IN DATABASE:')
print('='*60)
print(f"{'Ticker':8} {'Buy':>10} {'Sell':>10} {'Active':>8} {'Email ID'}")
print('-'*60)
for _, row in crypto_stocks.iterrows():
    buy = f"${row['buy_trade']:.2f}" if pd.notna(row['buy_trade']) else "N/A"
    sell = f"${row['sell_trade']:.2f}" if pd.notna(row['sell_trade']) else "N/A"
    print(f"{row['ticker']:8} {buy:>10} {sell:>10} {str(row['is_active']):>8} {row['source_email_id'][:8]}...")
    
print(f"\nTotal crypto stocks: {len(crypto_stocks)}")
print(f"Active: {len(crypto_stocks[crypto_stocks['is_active'] == True])}")
print(f"Inactive: {len(crypto_stocks[crypto_stocks['is_active'] == False])}")