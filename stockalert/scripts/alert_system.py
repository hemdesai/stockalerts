"""
Improved Alert System for StockAlert
Uses cached prices from the database for AM and PM sessions
"""
import os
import time
import json
import sqlite3
import pandas as pd
import requests
import logging
import yfinance as yf
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from stockalert.scripts.mcp_client import MCPClient

# Google API imports for service account (kept for fallback)
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AlertSystem")

class AlertSystem:
    def __init__(self):
        """Initialize the improved alert system"""
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        
        # Initialize MCP client for email operations
        self.mcp_client = MCPClient()
        self.using_mcp = self.mcp_client.connected
        
        if self.using_mcp:
            logger.info("Using MCP client for email operations")
        else:
            logger.warning("MCP client not connected, will use direct Gmail API for email operations")
        
        # Service account file path (for fallback)
        self.service_account_file = self.root_dir / 'credentials' / 'service_account.json'
        
        # Default recipient email
        self.recipient_email = os.environ.get('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
        
        # Buffer percentage for alerts (default 2%)
        self.buffer_pct = 2.0
        
        logger.info("Improved AlertSystem initialized")
    
    def get_current_session(self):
        """Determine if current time is AM or PM session"""
        now = datetime.now()
        if now.hour < 12:
            return "AM"
        return "PM"
    
    def get_latest_signals(self):
        """Get the latest signals from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get current session
            session = self.get_current_session()
            
            # Check if we have prices for the current session
            query = f"""
            SELECT COUNT(*) as count
            FROM stocks
            WHERE {session}_Price IS NOT NULL
            """
            
            df_count = pd.read_sql(query, conn)
            has_session_prices = df_count['count'].iloc[0] > 0
            
            # If we don't have prices for the current session, use the other session
            if not has_session_prices:
                other_session = "PM" if session == "AM" else "AM"
                logger.warning(f"No cached {session} prices available, trying {other_session} prices")
                
                # Check if we have prices for the other session
                query = f"""
                SELECT COUNT(*) as count
                FROM stocks
                WHERE {other_session}_Price IS NOT NULL
                """
                
                df_count = pd.read_sql(query, conn)
                has_other_session_prices = df_count['count'].iloc[0] > 0
                
                if has_other_session_prices:
                    session = other_session
                    logger.info(f"Using {session} prices instead")
                else:
                    logger.warning("No cached prices available in either session")
                    conn.close()
                    return None
            
            price_column = f"{session}_Price"
            
            # Get all stocks including sentiment and cached prices
            query = f"""
            SELECT 
                ticker, 
                sentiment, 
                name, 
                category, 
                buy_trade, 
                sell_trade, 
                {price_column} as current_price,
                Last_Price_Update
            FROM stocks
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            if df.empty:
                logger.warning("No stocks data available")
                return None
            
            # Filter out rows with missing prices
            df_with_prices = df.dropna(subset=['current_price'])
            
            # Check if we have any prices
            if df_with_prices.empty:
                logger.warning(f"No cached {session} prices available")
                return None
            
            # Check for stale prices (older than 24 hours)
            if 'Last_Price_Update' in df_with_prices.columns:
                df_with_prices['Last_Price_Update'] = pd.to_datetime(df_with_prices['Last_Price_Update'])
                now = datetime.now()
                df_with_prices = df_with_prices[
                    df_with_prices['Last_Price_Update'] > (now - timedelta(hours=24))
                ]
            
            logger.info(f"Retrieved {len(df_with_prices)} signals with valid {session} prices")
            return df_with_prices
            
        except Exception as e:
            logger.error(f"Error getting latest signals: {e}")
            return None
    
    def generate_alerts(self, buffer_pct=None):
        """Generate alerts based on cached prices in the database"""
        try:
            # Set buffer to 0 to remove any buffers
            buffer_pct = 0
            
            # Get signals with cached prices
            df = self.get_latest_signals()
            if df is None or df.empty:
                logger.warning("No signals with prices available for alert generation")
                return []
            
            # Get current session
            session = self.get_current_session()
            logger.info(f"Generating alerts for {session} session with no buffer")
            
            alerts = []
            for _, row in df.iterrows():
                ticker = row.get('ticker')
                name = row.get('name', ticker)
                category = row.get('category', 'unknown')
                buy_trade = row.get('buy_trade')
                sell_trade = row.get('sell_trade')
                sentiment = row.get('sentiment', '').upper()
                current_price = row.get('current_price')
                
                # Skip if required fields are missing or sentiment is NEUTRAL
                if (not ticker or pd.isna(buy_trade) or pd.isna(sell_trade) or 
                    pd.isna(current_price) or sentiment == "NEUTRAL"):
                    continue
                
                # Convert price values to float to ensure proper comparison
                try:
                    current_price = float(current_price)
                    buy_trade = float(buy_trade)
                    sell_trade = float(sell_trade)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid price values for {ticker}: current_price={current_price}, buy_trade={buy_trade}, sell_trade={sell_trade}")
                    continue
                
                # Determine alert type based on price position and sentiment
                alert_type = None
                threshold = None
                price_pct = None
                
                if sentiment == "BULLISH":
                    if current_price <= buy_trade:
                        alert_type = "BUY"
                        threshold = buy_trade
                        price_pct = ((buy_trade - current_price) / current_price) * 100
                    elif current_price >= sell_trade:
                        alert_type = "SELL"
                        threshold = sell_trade
                        price_pct = ((current_price - sell_trade) / sell_trade) * 100
                elif sentiment == "BEARISH":
                    if current_price <= buy_trade:
                        alert_type = "COVER"
                        threshold = buy_trade
                        price_pct = ((buy_trade - current_price) / current_price) * 100
                    elif current_price >= sell_trade:
                        alert_type = "SHORT"
                        threshold = sell_trade
                        price_pct = ((current_price - sell_trade) / sell_trade) * 100
                
                # Only create an alert if we have a valid alert type
                if alert_type:
                    alerts.append({
                        'ticker': ticker,
                        'name': name,
                        'current_price': current_price,
                        'threshold': threshold,
                        'type': alert_type,
                        'buy_trade': buy_trade,
                        'sell_trade': sell_trade,
                        'sentiment': sentiment,
                        'category': category,
                        'price_pct': price_pct,
                        'session': session,
                        'timestamp': datetime.now().isoformat()
                    })
            
            logger.info(f"Generated {len(alerts)} alerts for {session} session")
            return alerts
            
        except Exception as e:
            logger.error(f"Error generating alerts: {e}")
            return []
    
    def format_alert_email(self, alerts):
        """Format alerts into an HTML email"""
        if not alerts:
            return None
        
        # Group alerts by type
        alerts_by_type = {}
        for alert in alerts:
            alert_type = alert['type']
            if alert_type not in alerts_by_type:
                alerts_by_type[alert_type] = []
            alerts_by_type[alert_type].append(alert)
        
        # Get session
        session = alerts[0]['session']
        
        # Create HTML email
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #f0f0f0; padding: 10px; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th {{ background-color: #f0f0f0; text-align: left; padding: 8px; }}
                td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                .buy {{ color: green; }}
                .sell {{ color: red; }}
                .short {{ color: red; }}
                .cover {{ color: green; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Stock Alert System - {session} Session Alerts</h2>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        """
        
        # Add tables for each alert type
        for alert_type, type_alerts in alerts_by_type.items():
            css_class = alert_type.lower()
            html += f"""
            <h3 class="{css_class}">{alert_type} Alerts ({len(type_alerts)})</h3>
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Current Price</th>
                    <th>Target Price</th>
                    <th>Distance</th>
                </tr>
            """
            
            for alert in type_alerts:
                html += f"""
                <tr>
                    <td><strong>{alert['ticker']}</strong></td>
                    <td>{alert['name']}</td>
                    <td>{alert['category']}</td>
                    <td>${alert['current_price']:.2f}</td>
                    <td>${alert['threshold']:.2f}</td>
                    <td>{alert['price_pct']:.2f}%</td>
                </tr>
                """
            
            html += "</table>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, alerts):
        """Send alerts via email using MCP client or fallback to Gmail API"""
        if not alerts:
            logger.info("No alerts to send")
            return False
        
        try:
            # Format email content
            html_content = self.format_alert_email(alerts)
            if not html_content:
                logger.warning("Failed to format alert email")
                return False
            
            # Get session
            session = alerts[0]['session']
            
            # Create subject
            subject = f"Stock Alerts - {session} Session ({len(alerts)} alerts)"
            
            # First try using the MCP client if it's connected
            if self.using_mcp:
                logger.info(f"Attempting to send email via MCP: {subject}")
                success = self.mcp_client.send_email(subject, html_content, self.recipient_email)
                
                if success:
                    logger.info(f"Successfully sent email via MCP: {subject}")
                    return True
                else:
                    logger.warning("MCP client failed to send email, trying fallback method")
                    self.using_mcp = False  # Mark MCP as failed for future calls
            
            # If MCP client fails or is not connected, fall back to direct Gmail API
            logger.info(f"Using direct Gmail API to send email: {subject}")
            
            # Create message
            message = MIMEMultipart()
            message['to'] = self.recipient_email
            message['subject'] = subject
            
            # Attach HTML content
            msg = MIMEText(html_content, 'html')
            message.attach(msg)
            
            # Check if service account file exists
            if not os.path.exists(self.service_account_file):
                logger.error(f"Service account file not found: {self.service_account_file}")
                return False
            
            # Authenticate and send email
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            
            # Create Gmail API service
            service = build('gmail', 'v1', credentials=credentials)
            
            # Encode message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Create message body
            create_message = {
                'raw': encoded_message
            }
            
            # Send message
            send_message = service.users().messages().send(
                userId='me', 
                body=create_message
            ).execute()
            
            logger.info(f"Email sent with message ID: {send_message['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def check_mcp_connection(self):
        """Check if MCP connection is available and update status"""
        if not self.using_mcp:
            # Try to reconnect to MCP
            if self.mcp_client.check_connection():
                logger.info("Successfully reconnected to MCP server")
                self.using_mcp = True
                return True
            else:
                logger.warning("MCP server still not available")
                return False
        return True
    
    def run(self):
        """Run the alert system"""
        try:
            # Generate alerts
            logger.info("Starting to generate alerts...")
            alerts = self.generate_alerts()
            
            if not alerts:
                logger.info("No alerts to send")
                return []
            
            logger.info(f"Generated {len(alerts)} alerts. First alert: {alerts[0]}")
            
            # Format email
            html_content = self.format_alert_email(alerts)
            if not html_content:
                logger.warning("Failed to format alert email")
                return alerts
            
            logger.info(f"Email HTML content generated successfully (length: {len(html_content)})")
            
            # Send email
            subject = f"Stock Alerts - {alerts[0]['session']} Session"
            if self.using_mcp:
                # Use MCP client
                logger.info(f"Attempting to send email via MCP to {self.recipient_email}")
                success = self.mcp_client.send_email(
                    recipient=self.recipient_email,
                    subject=subject,
                    html_content=html_content
                )
                
                if success:
                    logger.info(f"Sent {len(alerts)} alerts via MCP")
                else:
                    logger.error("Failed to send alerts via MCP, trying fallback method")
                    self.send_email_via_gmail_api(subject, html_content)
            else:
                # Use fallback method
                logger.info("MCP not connected, using Gmail API fallback")
                self.send_email_via_gmail_api(subject, html_content)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error running alert system: {e}")
            return []
    
    def send_email_via_gmail_api(self, subject, html_content):
        # Create message
        message = MIMEMultipart()
        message['to'] = self.recipient_email
        message['subject'] = subject
        
        # Attach HTML content
        msg = MIMEText(html_content, 'html')
        message.attach(msg)
        
        # Check if service account file exists
        if not os.path.exists(self.service_account_file):
            logger.error(f"Service account file not found: {self.service_account_file}")
            return
        
        # Authenticate and send email
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        # Create Gmail API service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Encode message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Create message body
        create_message = {
            'raw': encoded_message
        }
        
        # Send message
        send_message = service.users().messages().send(
            userId='me', 
            body=create_message
        ).execute()
        
        logger.info(f"Email sent with message ID: {send_message['id']}")

if __name__ == "__main__":
    alert_system = AlertSystem()
    alerts = alert_system.run()
    
    if alerts:
        print(f"Generated {len(alerts)} alerts")
    else:
        print("No alerts generated")
