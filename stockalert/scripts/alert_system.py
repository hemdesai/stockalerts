import os
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Use the centralized environment loader
from stockalert.utils.env_loader import get_env, load_environment
from stockalert.scripts.email_service import EmailService

# Remove redundant environment loading since we're using the centralized loader
# load_dotenv()

class AlertSystem:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        
    def get_current_price(self, ticker):
        try:
            time.sleep(0.05)
            info = yf.Ticker(ticker).history(period="1d")
            if info.empty:
                print(f"No data available for {ticker}")
                return None
            return float(info['Close'].iloc[-1])
        except Exception as e:
            print(f"Error getting price for {ticker}: {str(e)}")
            return None

    def get_latest_signals(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            
            # Updated query to use our current database structure
            query = """
            SELECT a.ticker as Ticker, a.name as Name, a.category as Category, 
                   p.sentiment as Sentiment, p.buy_trade as 'Buy Trade', 
                   p.sell_trade as 'Sell Trade', p.current_price as 'Current Price'
            FROM assets a
            JOIN price_data p ON a.id = p.asset_id
            WHERE p.date = (SELECT MAX(date) FROM price_data)
            ORDER BY a.category, a.ticker
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"Error getting signals: {e}")
            return None
    
    def generate_alerts(self, df=None, buffer_pct=3.0):
        alerts = []  # ensure alerts list is always defined
        if df is None or df.empty:
            df = self.get_latest_signals()
            if df is None or df.empty:
                return []
            category_priority = {'ideas': 0, 'etfs': 1, 'digitalassets': 2, 'daily': 3}
            df['category_priority'] = df['Category'].map(category_priority)
            df = df.sort_values(['category_priority', 'Ticker']).drop('category_priority', axis=1)
            
        for _, row in df.iterrows():
            current_price = self.get_current_price(row['Ticker'])
            if current_price is None:
                continue
            buy_trade = row['Buy Trade']
            sell_trade = row['Sell Trade']
            sentiment = row['Sentiment'].upper()
            alert = {
                'ticker': row['Ticker'],
                'category': row['Category'],
                'sentiment': sentiment,
                'name': row['Name'],
                'current_price': current_price,
                # also store the original trade values for use in the email narrative
                'buy_trade': buy_trade,
                'sell_trade': sell_trade,
                'open_price': None,
                'close_price': None,
                'action': None,
                'profit': None
            }
            if sentiment == 'BULLISH':
                if current_price >= sell_trade:
                    profit = ((current_price - sell_trade) / sell_trade) * 100
                    alert.update({'action': 'Sell',
                                  'open_price': current_price,
                                  'close_price': sell_trade,
                                  'profit': profit})
                elif current_price <= buy_trade:
                    profit = ((buy_trade - current_price) / buy_trade) * 100
                    alert.update({'action': 'Buy',
                                  'open_price': current_price,
                                  'close_price': buy_trade,
                                  'profit': profit})
            elif sentiment == 'BEARISH':
                if current_price <= buy_trade:
                    profit = ((sell_trade - current_price) / sell_trade) * 100
                    alert.update({'action': 'Cover',
                                  'open_price': current_price,
                                  'close_price': sell_trade,
                                  'profit': profit})
                elif current_price > sell_trade:
                    profit = ((current_price - sell_trade) / sell_trade) * 100
                    alert.update({'action': 'Short',
                                  'open_price': current_price,
                                  'close_price': sell_trade,
                                  'profit': profit})
            if alert['action'] is not None:
                alerts.append(alert)
        return alerts

    def format_email_body(self, alerts):
        styles = """
        <style>
            .alert-card { padding: 10px; margin: 5px 0; border-radius: 4px; }
            .category-header { font-size: 18px; font-weight: bold; text-decoration: underline; margin: 20px 0 10px 0; }
            .bullish { border-left: 4px solid #006400; background-color: #f0fff0; }
            .bearish { border-left: 4px solid #8B0000; background-color: #fff0f0; }
            .alert-text { margin: 5px 0; font-family: Arial, sans-serif; }
            .category-divider { margin: 15px 0; border-top: 1px solid #eee; }
        </style>
        """
        
        # Define category priority
        category_priority = {'ideas': 0, 'etfs': 1, 'digitalassets': 2, 'daily': 3}
        
        # Group alerts by category and sort by priority
        alerts_by_category = {}
        for a in alerts:
            cat = a.get('category', 'Uncategorized')
            alerts_by_category.setdefault(cat, []).append(a)
        
        # Sort categories by priority
        sorted_categories = sorted(alerts_by_category.keys(), 
                                 key=lambda x: category_priority.get(x.lower(), 999))
        
        # Generate HTML with sorted categories
        html = styles
        alert_counter = 1
        for category in sorted_categories:
            html += f'<div class="category-header">{category.lower()}</div>'
            for a in alerts_by_category[category]:
                sentiment = a.get('sentiment', '')
                ticker = a.get('ticker', '')
                name = a.get('name', '')
                current = a.get('current_price', 0)
                action = a.get('action', '')
                profit = a.get('profit', 0)
                # For Sell and Short, use the stored buy_trade and sell_trade values
                if action in ['Sell', 'Short']:
                    open_val = a.get('buy_trade', 0)
                    close_val = a.get('sell_trade', 0)
                else:
                    open_val = a.get('open_price', 0)
                    close_val = a.get('close_price', 0)
                # Label: 'gain' for bullish, 'profit' for bearish
                label = 'gain' if sentiment == 'BULLISH' else 'profit'
                profit_str = f"{'+' if profit>=0 else ''}{profit:.1f}%"
                narrative = (f"{alert_counter}. {ticker} ({name}) at ${current:.2f} → {action} "
                             f"(${a.get('buy_trade', 0):.2f}-${a.get('sell_trade', 0):.2f} {sentiment.lower()}) for {profit_str} {label}")
                css_class = 'bullish' if sentiment == 'BULLISH' else 'bearish'
                html += f'<div class="alert-card {css_class}"><p class="alert-text">{narrative}</p></div>'
                alert_counter += 1
            html += '<div class="category-divider"></div>'
        return html

    def send_email_alert(self, alerts):
        try:
            # Use the new EmailService for sending alerts
            email_service = EmailService()
            
            # Send email alerts
            result = email_service.send_alert_email(alerts)
            
            if result:
                print("Alert email sent successfully!")
                logging.info(f"Alert email sent successfully with {len(alerts)} alerts")
            else:
                print("Failed to send alert email")
                logging.error("Failed to send alert email")
                
        except Exception as e:
            error_msg = f"Error sending email: {e}"
            print(error_msg)
            logging.error(error_msg)

    def run(self):
        print("Starting Alert System...")
        alerts = self.generate_alerts()
        if alerts:
            print(f"Generated {len(alerts)} alerts")
            self.send_email_alert(alerts)
        else:
            print("No alerts generated")

if __name__ == "__main__":
    AlertSystem().run()
