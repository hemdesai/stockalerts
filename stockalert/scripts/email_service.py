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
# Import MCP client
from stockalert.scripts.mcp_client import MCPClient

# Function to check if a ticker is an index, interest rate, currency or other special asset type
def is_special_asset(ticker, category=None):
    return (ticker.startswith('^') or 
            '=' in ticker or 
            ticker in ['TYX', '2YY', '5YY', '10Y', '30Y', 'DXY', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD'] or
            ticker.endswith('USD') or ticker.endswith('EUR') or ticker.endswith('GBP') or ticker.endswith('JPY') or
            ticker.endswith('CHF') or ticker.endswith('CAD') or ticker.endswith('AUD') or ticker.endswith('NZD') or
            (category and category.lower() == 'digitalassets'))

# Function to format price based on asset type
def format_price(price, ticker, category=None):
    if is_special_asset(ticker, category):
        return f"{price:.2f}"
    else:
        return f"${price:.2f}"

class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        """Initialize the email service with credentials from environment variables"""
        self.root_dir = Path(__file__).parent.parent
        self.service_account_path = self.root_dir / 'credentials' / 'service_account.json'
        
        # Set up email credentials
        self.sender_email = get_env('EMAIL_SENDER', 'hemdesai@gmail.com')
        self.app_password = get_env('EMAIL_PASSWORD', 'gizp vnlz nmgc lowo')
        self.recipient_email = get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
        
        # Initialize MCP client
        self.mcp_client = MCPClient()
        
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
        """Authorize with Google Sheets API using service account (fallback method)"""
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(str(self.service_account_path), scope)
            return gspread.authorize(creds)
        except Exception as e:
            logging.error(f"Error authorizing with Google Sheets: {e}")
            return None
    
    def write_alerts_to_sheet(self, alerts, sheet_name='research', tab_name=None):
        """Write alerts to Google Sheet using MCP server"""
        try:
            # Determine if AM or PM alert based on current hour (EST)
            import pytz
            est = pytz.timezone('US/Eastern')
            current_hour = datetime.datetime.now(est).hour
            
            if tab_name is None:
                tab_name = 'am_alerts' if current_hour < 12 else 'pm_alerts'
            
            # Format alerts for sheet
            formatted_alerts = []
            for alert in alerts:
                timestamp = datetime.datetime.now().isoformat()
                date_val = datetime.datetime.now().strftime('%Y-%m-%d')
                
                formatted_alert = {
                    "timestamp": timestamp,
                    "date": date_val,
                    "ticker": alert.get('ticker', ''),
                    "sentiment": alert.get('sentiment', ''),
                    "name": alert.get('name', ''),
                    "action": alert.get('action', ''),
                    "current_price": alert.get('current_price', 0),
                    "buy_trade": alert.get('buy_trade', 0),
                    "sell_trade": alert.get('sell_trade', 0),
                    "category": alert.get('category', '')
                }
                
                formatted_alerts.append(formatted_alert)
            
            # Try using MCP client first
            success = self.mcp_client.write_to_sheet(sheet_name, formatted_alerts, tab_name)
            
            if success:
                logging.info(f"Successfully wrote {len(alerts)} alerts to {sheet_name}/{tab_name} via MCP server")
                return True
                
            # Fall back to direct Google Sheets API if MCP fails
            logging.warning("MCP server failed, falling back to direct Google Sheets API")
            
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
            headers = ["timestamp", "date", "ticker", "sentiment", "name", "action", "current_price", "buy_trade", "sell_trade", "category"]
            
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
                    alert.get('category', '')
                ]
                
                ws.append_row(row)
            
            logging.info(f"Successfully wrote {len(alerts)} alerts to {sheet_name}/{tab_name} via direct API")
            return True
        except Exception as e:
            logging.error(f"Error writing alerts to sheet: {e}")
            return False
    
    def send_email(self, subject, html_content):
        """Send an email using MCP server with fallback to SMTP"""
        try:
            # Try using MCP client first
            success = self.mcp_client.send_email(subject, html_content, self.recipient_email)
            
            if success:
                logging.info(f"Email sent successfully via MCP server: {subject}")
                return True
                
            # Fall back to direct SMTP if MCP fails
            logging.warning("MCP server failed, falling back to direct SMTP")
            
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
                
            logging.info(f"Email sent successfully via direct SMTP: {subject}")
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
                category = a.get('category', '')
                
                # Format prices based on asset type
                current_price_display = format_price(current, ticker, category)
                buy_trade_display = format_price(a.get('buy_trade', 0), ticker, category)
                sell_trade_display = format_price(a.get('sell_trade', 0), ticker, category)
                
                narrative = (f"{alert_counter}. {ticker} ({name}) at {current_price_display} → {action} "
                            f"({buy_trade_display}-{sell_trade_display} {sentiment.lower()})")
                
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
