import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# Fix for alerts section
import glob
import re
from datetime import datetime

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Load environment variables
try:
    from stockalert.utils.env_loader import get_env, load_environment
    load_environment()
except ImportError:
    # Fallback if module not found
    def get_env(key, default=None):
        return os.environ.get(key, default)
    
    def load_environment():
        # Load from .env file if available
        env_path = project_root / '.env'
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value

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

# Set page config
st.set_page_config(
    page_title="StockAlert Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme styling
st.markdown("""
<style>
    /* Set background and text colors for dark mode */
    body, .stApp {
        background-color: #181c20 !important;
        color: #e0e0e0 !important;
    }
    .stApp {
        background-color: #181c20 !important;
    }
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1a1d23 !important;
        color: #e0e0e0 !important;
    }
    /* Table and dataframe styling */
    .stDataFrame, .stTable, .stMarkdown, .stText, .stSelectbox, .stButton, .stAlert {
        background-color: #23272e !important;
        color: #e0e0e0 !important;
    }
    /* Section headers */
    .section-header h2 {
        color: #F0B90B !important;
        background: #23272e;
        padding: 0.5rem 1rem;
        border-radius: 0.4rem;
        margin-bottom: 0.5rem;
    }
    /* Dashboard title */
    .dashboard-title {
        font-size: 2.5rem;
        color: #00CFFF !important;
        font-weight: bold;
        margin-bottom: 1.5rem;
    }
    /* Stat columns */
    .bullish {
        color: #0ECB81 !important;
        font-weight: bold;
    }
    .bearish {
        color: #F6465D !important;
        font-weight: bold;
    }
    .neutral {
        color: #F0B90B !important;
        font-weight: bold;
    }
    /* Dataframe header and cell styling */
    .stDataFrame th, .stDataFrame td {
        background-color: #23272e !important;
        color: #e0e0e0 !important;
    }
    /* Buttons */
    .stButton>button {
        background-color: #23272e !important;
        color: #F0B90B !important;
        border-radius: 0.3rem;
        font-weight: bold;
        border: 1px solid #F0B90B;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .highlight {
        background-color: #f0f2f6;
        padding: 5px;
        border-radius: 3px;
    }
    .profit {
        color: #0ECB81;
    }
    .loss {
        color: #F6465D;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="dashboard-title">📈 StockAlert Dashboard</div>', unsafe_allow_html=True)

# Select sentiment
sentiment = st.sidebar.selectbox(
    "Select Sentiment",
    ["All", "BULLISH", "BEARISH", "NEUTRAL"]
)

# Refresh button
if st.sidebar.button("Refresh Data"):
    st.sidebar.success("Data refreshed!")

    # Main content
    # Load asset data directly from SQLite
    conn = sqlite3.connect(Path(__file__).parent / 'data' / 'stocks.db')
    query = (
        "SELECT ticker, name, category, sentiment, buy_trade, sell_trade, "
        "COALESCE(PM_Price, AM_Price) AS current_price FROM stocks"
    )
    filters = []
    if sentiment != "All":
        filters.append(f"sentiment = '{sentiment}'")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Convert to DataFrame
    if not df.empty:
        # Format DataFrame
        if 'current_price' in df.columns:
            df['current_price'] = df['current_price'].astype(float).round(2)
        if 'buy_trade' in df.columns:
            df['buy_trade'] = df['buy_trade'].astype(float).round(2)
        if 'sell_trade' in df.columns:
            df['sell_trade'] = df['sell_trade'].astype(float).round(2)
        
        # Display summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"### 🏷️ Total Assets")
            st.markdown(f"<h2>{len(df)}</h2>", unsafe_allow_html=True)
        with col2:
            if 'sentiment' in df.columns:
                bullish_count = len(df[df['sentiment'] == 'BULLISH'])
                st.markdown(f"### 🔼 Bullish")
                st.markdown(f"<h2 class='bullish'>{bullish_count}</h2>", unsafe_allow_html=True)
        with col3:
            if 'sentiment' in df.columns:
                bearish_count = len(df[df['sentiment'] == 'BEARISH'])
                st.markdown(f"### 🔽 Bearish")
                st.markdown(f"<h2 class='bearish'>{bearish_count}</h2>", unsafe_allow_html=True)
        with col4:
            if 'sentiment' in df.columns:
                neutral_count = len(df[df['sentiment'] == 'NEUTRAL'])
                st.markdown(f"### ➡️ Neutral")
                st.markdown(f"<h2 class='neutral'>{neutral_count}</h2>", unsafe_allow_html=True)

        # Asset Data section with styled header
        st.markdown('<div class="section-header"><h2>📋 Asset Data</h2></div>', unsafe_allow_html=True)
        st.dataframe(df)

        # Alerts Generated Today section
        st.markdown('<div class="section-header"><h2>🚨 Alerts Generated Today</h2></div>', unsafe_allow_html=True)
        html_files = glob.glob(str(Path(__file__).parent / 'data' / 'email_alerts_*.html'))
        if html_files:
            latest_file = max(html_files, key=os.path.getctime)
            with open(latest_file, 'r') as f:
                html_content = f.read()
            # Extract the timestamp from the HTML
            timestamp_match = re.search(r'<h2>Stock Alerts \((.*?)\)</h2>', html_content)
            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
            # Extract alert data using regex
            alert_pattern = re.compile(r'(\d+)\. ([\w\^=\-\.]+) \((.*?)\) at (\$?[\d\.]+) -> ([\w\s]+) \((\$?[\d\.]+)-(\$?[\d\.]+) ([\w]+)\) for ([+-]?[\d\.]+)% ([\w]+)')
            alerts_data = []
            for match in alert_pattern.finditer(html_content):
                num, ticker, name, current_price, action, buy_price, sell_price, sentiment, profit_pct, profit_type = match.groups()
                current_price = current_price.replace('$', '')
                buy_price = buy_price.replace('$', '')
                sell_price = sell_price.replace('$', '')
                alerts_data.append({
                    "ticker": ticker,
                    "name": name,
                    "sentiment": sentiment,
                    "current_price": float(current_price),
                    "buy_trade": float(buy_price),
                    "sell_trade": float(sell_price),
                    "action": action
                })
            if alerts_data:
                alerts_table = pd.DataFrame(alerts_data)
                st.write(f"Generated on: {timestamp}")
                st.dataframe(alerts_table, use_container_width=True)
            else:
                st.info("No alerts found in the email content")
        else:
            st.info("No alert emails found for today.")
    else:
        st.info("No data found for the selected filters")