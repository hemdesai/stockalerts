import os, time, sqlite3
import pandas as pd, yfinance as yf, pytz
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

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
            query = "SELECT * FROM stocks ORDER BY Category, Ticker"
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
        html = styles
        alerts_by_category = {}
        for a in alerts:
            cat = a.get('category', 'Uncategorized')
            alerts_by_category.setdefault(cat, []).append(a)
        alert_counter = 1
        for category, cat_alerts in alerts_by_category.items():
            html += f'<div class="category-header">{category.lower()}</div>'
            for a in cat_alerts:
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
                             f"(${open_val:.2f}-${close_val:.2f} {sentiment.lower()}) for {profit_str} {label}")
                css_class = 'bullish' if sentiment == 'BULLISH' else 'bearish'
                html += f'<div class="alert-card {css_class}"><p class="alert-text">{narrative}</p></div>'
                alert_counter += 1
            html += '<div class="category-divider"></div>'
        return html

    def send_email_alert(self, alerts):
        try:
            sender = os.getenv('EMAIL_SENDER')
            password = os.getenv('EMAIL_PASSWORD')
            recipient = os.getenv('EMAIL_RECIPIENT')
            est = pytz.timezone('US/Eastern')
            now_est = datetime.now(est)
            title = f"{len(alerts)} Trade Alert{'s' if len(alerts)!=1 else ''} - {now_est.strftime('%d/%m %H:%M')} EST"
            msg = MIMEMultipart('alternative')
            msg['Subject'] = title
            msg['From'] = sender
            msg['To'] = recipient
            html_body = self.format_email_body(alerts)
            msg.attach(MIMEText(html_body, 'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender, password)
                server.send_message(msg)
                print("Alert email sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")

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
