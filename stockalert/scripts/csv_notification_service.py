import os
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
import pytz
from stockalert.utils.env_loader import get_env

# Load environment variables
# load_dotenv()

class CSVNotificationService:
    """Service to send notifications about CSV updates and schedule database imports"""
    
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.data_dir = self.root_dir / 'data'
        self.sender_email = get_env('EMAIL_SENDER', 'hemdesai@gmail.com')
        self.app_password = get_env('EMAIL_PASSWORD', 'gizp vnlz nmgc lowo')
        self.recipient_email = get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
        self.ny_tz = pytz.timezone('America/New_York')
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.data_dir / 'csv_notification.log'),
                logging.StreamHandler()
            ]
        )
    
    def check_csv_files(self):
        """Check if all CSV files exist and get their stats"""
        csv_files = {
            'daily': self.data_dir / 'daily.csv',
            'digitalassets': self.data_dir / 'digitalassets.csv',
            'etfs': self.data_dir / 'etfs.csv',
            'ideas': self.data_dir / 'ideas.csv'
        }
        
        results = {}
        all_exist = True
        
        for category, file_path in csv_files.items():
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    results[category] = {
                        'exists': True,
                        'row_count': len(df),
                        'last_modified': last_modified,
                        'sample': df.head(3).to_dict('records') if not df.empty else []
                    }
                except Exception as e:
                    results[category] = {
                        'exists': True,
                        'error': str(e),
                        'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                    }
            else:
                results[category] = {
                    'exists': False
                }
                all_exist = False
        
        return {
            'all_exist': all_exist,
            'files': results
        }
    
    def send_csv_notification(self):
        """Send an email notification about the CSV files"""
        try:
            csv_status = self.check_csv_files()
            
            if not csv_status['all_exist']:
                logging.warning("Not all CSV files exist, cannot send notification")
                return False
            
            # Create email subject
            now_est = datetime.now(self.ny_tz)
            subject = f"CSV Files Updated - {now_est.strftime('%d/%m/%Y %H:%M')} EST"
            
            # Create HTML content with simpler styling
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>CSV Files Status - {now_est.strftime('%d/%m/%Y %H:%M')} EST</h2>
                <p>The following CSV files have been updated and are ready for review:</p>
                
                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">Category</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">Rows</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">Last Modified</th>
                    </tr>
            """
            
            # Add file information
            for category, info in csv_status['files'].items():
                if info['exists']:
                    row_count = info.get('row_count', 'Error')
                    last_modified = info.get('last_modified', 'Unknown').strftime('%H:%M:%S')
                    
                    html += f"""
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{category}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{row_count}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{last_modified}</td>
                    </tr>
                    """
            
            html += """
                </table>
                
                <h3>Sample Data</h3>
            """
            
            # Add sample data for each file
            for category, info in csv_status['files'].items():
                if info['exists'] and 'sample' in info and info['sample']:
                    html += f"<h4>{category}</h4>"
                    html += "<table style='border-collapse: collapse; width: 100%;'><tr>"
                    
                    # Add headers
                    for key in info['sample'][0].keys():
                        html += f"<th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;'>{key}</th>"
                    html += "</tr>"
                    
                    # Add data rows
                    for row in info['sample']:
                        html += "<tr>"
                        for key, value in row.items():
                            html += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: left;'>{value}</td>"
                        html += "</tr>"
                    
                    html += "</table>"
            
            html += """
                <p>Please review the CSV files for any issues before the database import at 10:55 AM EST.</p>
                <p>The database import will automatically delete existing records for today before adding the new data.</p>
            </body>
            </html>
            """
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # Add HTML content
            msg.attach(MIMEText(html, 'html'))
            
            # Send the email
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)
            
            logging.info("CSV notification email sent successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error sending CSV notification: {e}")
            return False
