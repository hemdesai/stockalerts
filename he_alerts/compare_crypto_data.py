"""
Compare extracted crypto data with current database values.
"""
import pandas as pd

# Current database values
db_data = {
    'BTC': {'buy': 116612.00, 'sell': 120218.00},
    'ETH': {'buy': 3353.00, 'sell': 3924.00},
    'SOL': {'buy': 171.00, 'sell': 205.00},
    'AVAX': {'buy': 22.28, 'sell': 26.01},
    'AAVE': {'buy': 287.00, 'sell': 337.00},
    'IBIT': {'buy': 65.19, 'sell': 69.17},
    'MSTR': {'buy': 405.00, 'sell': 465.00},
    'MARA': {'buy': 17.11, 'sell': 20.40},
    'RIOT': {'buy': 11.97, 'sell': 14.97},
    'COIN': {'buy': 378.00, 'sell': 425.00},
    'BITO': {'buy': 22.03, 'sell': 23.51},
    'ETHA': {'buy': 22.49, 'sell': 29.86},
    'BLOK': {'buy': 58.21, 'sell': 62.91}
}

# Correctly extracted values
correct_data = {
    'BTC': {'buy': 114852.00, 'sell': 120467.00},
    'ETH': {'buy': 3455.00, 'sell': 3896.00},
    'SOL': {'buy': 170.00, 'sell': 205.00},
    'AVAX': {'buy': 22.50, 'sell': 26.07},
    'AAVE': {'buy': 283.00, 'sell': 338.00},
    'IBIT': {'buy': 65.22, 'sell': 69.00},
    'MSTR': {'buy': 401.00, 'sell': 460.00},
    'MARA': {'buy': 17.01, 'sell': 20.44},
    'RIOT': {'buy': 12.97, 'sell': 15.48},
    'COIN': {'buy': 381.00, 'sell': 424.00},
    'BITO': {'buy': 22.01, 'sell': 25.52},
    'ETHA': {'buy': 22.99, 'sell': 30.39},
    'BLOK': {'buy': 58.41, 'sell': 62.90}
}

print("COMPARISON: Database vs Correct Values")
print("=" * 80)
print(f"{'Ticker':8} {'DB Buy':>12} {'Correct Buy':>12} {'Diff':>12} | {'DB Sell':>12} {'Correct Sell':>12} {'Diff':>12}")
print("-" * 80)

for ticker in sorted(db_data.keys()):
    db_buy = db_data[ticker]['buy']
    db_sell = db_data[ticker]['sell']
    correct_buy = correct_data[ticker]['buy']
    correct_sell = correct_data[ticker]['sell']
    
    buy_diff = correct_buy - db_buy
    sell_diff = correct_sell - db_sell
    
    # Highlight significant differences
    buy_mark = "***" if abs(buy_diff) > 1 else ""
    sell_mark = "***" if abs(sell_diff) > 1 else ""
    
    print(f"{ticker:8} ${db_buy:>11,.2f} ${correct_buy:>11,.2f} ${buy_diff:>11,.2f}{buy_mark:3} | ${db_sell:>11,.2f} ${correct_sell:>11,.2f} ${sell_diff:>11,.2f}{sell_mark:3}")

print("\n*** = Significant difference (>$1)")