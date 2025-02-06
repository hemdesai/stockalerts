import os
import pandas as pd
import sqlite3
import yfinance as yf
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv # type: ignore
import time  # Add this import at the top
import pytz

# Load environment variables
load_dotenv()

class AlertSystem:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        
    def get_current_price(self, ticker):
        """Get current price using yfinance with delay"""
        try:
            time.sleep(0.05)  # Reduced delay
            info = yf.Ticker(ticker).history(period="1d")
            if info.empty:
                print(f"No data available for {ticker}")
                return None
            
            current_price = info['Close'].iloc[-1]
            return float(current_price)
        except Exception as e:
            print(f"Error getting price for {ticker}: {str(e)}")
            return None

    def get_latest_signals(self):
        """Get the trading signals from database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            query = """
            SELECT * FROM stocks 
            ORDER BY Category, Ticker
            """
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"Error getting signals: {e}")
            return None

    def generate_alerts(self, buffer_pct=3.0):
        """Generate alerts based on trading signals with custom buffer"""
        buffer = buffer_pct / 100
        df = self.get_latest_signals()
        if df is None or df.empty:
            return []

        alerts = []
        
        for _, row in df.iterrows():
            current_price = self.get_current_price(row['Ticker'])
            if current_price is None:
                continue

            alert_data = {
                'ticker': row['Ticker'],
                'category': row['Category'],
                'sentiment': row['Sentiment'],
                'name': row['Name'],
                'current_price': current_price,
                'open_price': None,
                'open_signal': None,
                'open_pct': None,
                'close_price': None,
                'close_signal': None,
                'close_pct': None
            }

            if row['Sentiment'] == 'BULLISH':
                # Buy signal check
                buy_pct = (row['Buy Trade'] - current_price) / current_price * 100
                if buy_pct > buffer_pct:
                    alert_data.update({
                        'open_price': row['Buy Trade'],
                        'open_signal': 'Buy',
                        'open_pct': buy_pct
                    })

                # Sell signal check
                sell_pct = (current_price - row['Sell Trade']) / row['Sell Trade'] * 100
                if sell_pct > buffer_pct:
                    alert_data.update({
                        'close_price': row['Sell Trade'],
                        'close_signal': 'Sell',
                        'close_pct': sell_pct
                    })

            elif row['Sentiment'] == 'BEARISH':
                # Short signal check
                short_pct = (current_price - row['Sell Trade']) / row['Sell Trade'] * 100
                if short_pct > buffer_pct:
                    alert_data.update({
                        'open_price': row['Sell Trade'],
                        'open_signal': 'Short',
                        'open_pct': short_pct
                    })

                # Cover signal check
                cover_pct = (row['Buy Trade'] - current_price) / current_price * 100
                if cover_pct > buffer_pct:
                    alert_data.update({
                        'close_price': row['Buy Trade'],
                        'close_signal': 'Cover',
                        'close_pct': cover_pct
                    })

            # Only add to alerts if there's at least one signal
            if alert_data['open_signal'] is not None or alert_data['close_signal'] is not None:
                alerts.append(alert_data)

        return alerts

    def format_email_body(self, alerts):
        """Format alerts into HTML email body with improved styling"""
        if not alerts:
            return "<p>No trading signals triggered.</p>"
        
        # Add CSS styles
        html = """
        <style>
            .alert-table {
                border-collapse: collapse;
                width: 100%;
                max-width: 1200px;
                margin: 20px auto;
                background-color: #ffffff;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                font-family: Arial, sans-serif;
            }
            .alert-table th {
                background-color: #f8f9fa;
                color: #202124;
                padding: 12px;
                text-align: left;
                font-weight: bold;
                border-bottom: 2px solid #dee2e6;
            }
            .alert-table td {
                padding: 10px;
                border-bottom: 1px solid #dee2e6;
            }
            .alert-table tr:hover {
                background-color: #f5f5f5;
            }
            .green { color: #28a745; }
            .red { color: #dc3545; }
            .header {
                background-color: #f8f9fa;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
                text-align: center;
            }
            .timestamp {
                color: #666;
                font-size: 14px;
                margin-top: 5px;
            }
        </style>
        """
        
        # Add header with timestamp
        est = pytz.timezone('US/Eastern')
        current_time = datetime.now(est).strftime("%B %d, %Y %H:%M EST")
        html += f"""
        <div class="header">
            <h2>Trading Alerts</h2>
            <div class="timestamp">Generated on {current_time}</div>
        </div>
        """
        
        # Create table
        html += '<table class="alert-table">'
        html += """
            <tr>
                <th>Ticker</th>
                <th>Category</th>
                <th>Current</th>
                <th>Open Price</th>
                <th>Open Signal</th>
                <th>Open %</th>
                <th>Close Price</th>
                <th>Close Signal</th>
                <th>Close %</th>
            </tr>
        """
        
        for alert in alerts:
            html += "<tr>"
            html += f"<td><strong>{alert['ticker']}</strong></td>"
            html += f"<td>{alert['category']}</td>"
            html += f"<td>${alert['current_price']:.2f}</td>"
            
            # Open signals
            if alert['open_signal']:
                signal_color = 'green' if alert['open_signal'] in ['Buy', 'Cover'] else 'red'
                html += f"<td>${alert['open_price']:.2f}</td>"
                html += f"<td class='{signal_color}'>{alert['open_signal']}</td>"
                html += f"<td>{alert['open_pct']:+.1f}%</td>"
            else:
                html += "<td>-</td><td>-</td><td>-</td>"
            
            # Close signals
            if alert['close_signal']:
                signal_color = 'green' if alert['close_signal'] in ['Buy', 'Cover'] else 'red'
                html += f"<td>${alert['close_price']:.2f}</td>"
                html += f"<td class='{signal_color}'>{alert['close_signal']}</td>"
                html += f"<td>{alert['close_pct']:+.1f}%</td>"
            else:
                html += "<td>-</td><td>-</td><td>-</td>"
            
            html += "</tr>"
        
        html += "</table>"
        return html

    def send_email_alert(self, alerts):
        """Send email with trading alerts"""
        try:
            sender_email = os.getenv('EMAIL_SENDER')
            sender_password = os.getenv('EMAIL_PASSWORD')
            recipient_email = os.getenv('EMAIL_RECIPIENT')

            # Get EST time
            est = pytz.timezone('US/Eastern')
            est_time = datetime.now(est)
            
            # Format title with count and EST time
            alert_count = len(alerts)
            title = f"{alert_count} Trade Alert{'s' if alert_count != 1 else ''} - {est_time.strftime('%d/%m %H:%M')} EST"

            msg = MIMEMultipart('alternative')
            msg['Subject'] = title
            msg['From'] = sender_email
            msg['To'] = recipient_email

            html_body = self.format_email_body(alerts)
            msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
                print("Alert email sent successfully!")

        except Exception as e:
            print(f"Error sending email: {e}")

    def run(self):
        """Main function to run the alert system"""
        print("Starting Alert System...")
        alerts = self.generate_alerts()
        if alerts:
            print(f"Generated {len(alerts)} alerts")
            self.send_email_alert(alerts)
        else:
            print("No alerts generated")

if __name__ == "__main__":
    alert_system = AlertSystem()
    alert_system.run()