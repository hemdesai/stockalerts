from schwab_api import SchwabAPI  # You'll need to provide the actual Schwab API package
import pandas as pd
import os

class PriceFetcher:
    def __init__(self):
        self.api = SchwabAPI(
            client_id=os.getenv('SCHWAB_CLIENT_ID'),
            client_secret=os.getenv('SCHWAB_CLIENT_SECRET')
        )
    
    def get_current_price(self, ticker):
        try:
            quote = self.api.get_quote(ticker)
            return float(quote['last_price'])
        except Exception as e:
            print(f"Error fetching price for {ticker}: {e}")
            return None 