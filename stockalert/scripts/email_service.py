import os
import base64
import email
from bs4 import BeautifulSoup
import re
import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
from pathlib import Path
from dotenv import load_dotenv

# Use the centralized environment loader
from stockalert.utils.env_loader import get_env

class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        """Initialize the email service with credentials from environment variables"""
        self.root_dir = Path(__file__).parent.parent
        self.service_account_path = self.root_dir.parent / 'service_account.json'
        
        # Set up email credentials
        self.sender_email = get_env('EMAIL_SENDER', 'hemdesai@gmail.com')
        self.app_password = get_env('EMAIL_PASSWORD', 'gizp vnlz nmgc lowo')
        self.recipient_email = get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.root_dir / 'data' / 'email_service.log'),
                logging.StreamHandler()
            ]
        )
    
    def authorize_gspread(self):
        """Authorize with Google Sheets API using service account"""
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(str(self.service_account_path), scope)
            return gspread.authorize(creds)
        except Exception as e:
            logging.error(f"Error authorizing with Google Sheets: {e}")
            return None
    
    def write_alerts_to_sheet(self, alerts, sheet_name='research', tab_name=None):
        """Write alerts to Google Sheet"""
        try:
            # Determine if AM or PM alert based on current hour (EST)
            import pytz
            est = pytz.timezone('US/Eastern')
            current_hour = datetime.datetime.now(est).hour
            
            if tab_name is None:
                tab_name = 'am_alerts' if current_hour < 12 else 'pm_alerts'
            
            # Connect to Google Sheets
            gs_client = self.authorize_gspread()
            if not gs_client:
                logging.error("Failed to authorize with Google Sheets")
                return False
                
            # Open the sheet and worksheet
            sheet = gs_client.open(sheet_name)
            ws = sheet.worksheet(tab_name)
            
            # Check and set headers if needed
            existing_data = ws.get_all_values()
            headers = ["Timestamp", "Date", "Ticker", "Sentiment", "Name", "Action", "Current Price", "Buy Trade", "Sell Trade", "Profit %"]
            
            if not existing_data or existing_data[0] != headers:
                ws.clear()
                ws.append_row(headers)
            
            # Add alerts to sheet
            for alert in alerts:
                timestamp = datetime.datetime.now().isoformat()
                date_val = datetime.datetime.now().strftime('%Y-%m-%d')
                
                row = [
                    timestamp,
                    date_val,
                    alert.get('ticker', ''),
                    alert.get('sentiment', ''),
                    alert.get('name', ''),
                    alert.get('action', ''),
                    alert.get('current_price', 0),
                    alert.get('buy_trade', 0),
                    alert.get('sell_trade', 0),
                    f"{alert.get('profit', 0):.2f}%"
                ]
                
                ws.append_row(row)
            
            logging.info(f"Successfully wrote {len(alerts)} alerts to {sheet_name}/{tab_name}")
            return True
        except Exception as e:
            logging.error(f"Error writing alerts to sheet: {e}")
            return False
    
    def send_email(self, subject, html_content):
        """Send an email using Gmail SMTP with app password"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send the email via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)
                
            logging.info(f"Email sent successfully: {subject}")
            return True
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            return False
    
    def send_alert_email(self, alerts):
        """Format and send alert email"""
        if not alerts:
            logging.info("No alerts to send")
            return False
            
        # Determine if it's AM or PM alert based on current hour (EST)
        import pytz
        est = pytz.timezone('US/Eastern')
        now_est = datetime.datetime.now(est)
        current_hour_est = now_est.hour
        alert_time = 'AM' if current_hour_est < 12 else 'PM'
        
        # Create email subject
        subject = f"{len(alerts)} {alert_time} Trade Alert{'s' if len(alerts)!=1 else ''} - {now_est.strftime('%d/%m %H:%M')} EST"
        
        # Create HTML content
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .alert-card { 
                    padding: 10px; 
                    margin: 10px 0; 
                    border-radius: 5px; 
                }
                .bullish { 
                    background-color: #e6ffe6; 
                    border-left: 5px solid #00cc00; 
                }
                .bearish { 
                    background-color: #ffe6e6; 
                    border-left: 5px solid #cc0000; 
                }
                .alert-text { margin: 0; }
                .category-divider { 
                    border-top: 1px dashed #ccc; 
                    margin: 15px 0; 
                }
            </style>
        </head>
        <body>
            <h2>Trade Alerts - {date}</h2>
        """.format(date=now_est.strftime('%d/%m/%Y %H:%M') + ' EST')
        
        # Group alerts by category
        alerts_by_category = {}
        for alert in alerts:
            category = alert.get('category', 'Unknown')
            if category not in alerts_by_category:
                alerts_by_category[category] = []
            alerts_by_category[category].append(alert)
        
        # Add alerts to HTML
        alert_counter = 1
        for category in sorted(alerts_by_category.keys()):
            html += f'<h3>{category}</h3>'
            
            for a in alerts_by_category[category]:
                sentiment = a.get('sentiment', '')
                ticker = a.get('ticker', '')
                name = a.get('name', '')
                current = a.get('current_price', 0)
                action = a.get('action', '')
                profit = a.get('profit', 0)
                
                # Label: 'gain' for bullish, 'profit' for bearish
                label = 'gain' if sentiment == 'BULLISH' else 'profit'
                profit_str = f"{'+' if profit>=0 else ''}{profit:.1f}%"
                
                narrative = (f"{alert_counter}. {ticker} ({name}) at ${current:.2f} → {action} "
                            f"(${a.get('buy_trade', 0):.2f}-${a.get('sell_trade', 0):.2f} {sentiment.lower()}) for {profit_str} {label}")
                
                css_class = 'bullish' if sentiment == 'BULLISH' else 'bearish'
                html += f'<div class="alert-card {css_class}"><p class="alert-text">{narrative}</p></div>'
                alert_counter += 1
                
            html += '<div class="category-divider"></div>'
        
        html += """
        </body>
        </html>
        """
        
        # Send the email
        result = self.send_email(subject, html)
        
        # Also write to Google Sheet
        self.write_alerts_to_sheet(alerts)
        
        return result
