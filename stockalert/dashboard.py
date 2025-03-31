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

# Import the database manager
from stockalert.scripts.db_manager import StockAlertDBManager

# Initialize the database manager
db_manager = StockAlertDBManager()

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

# Custom CSS for styling
st.markdown("""
<style>
    .bullish {
        color: #0ECB81;
        font-weight: bold;
    }
    .bearish {
        color: #F6465D;
        font-weight: bold;
    }
    .neutral {
        color: #F0B90B;
        font-weight: bold;
    }
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .section-header {
        background-color: #f0f2f6;
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

# Sidebar
st.sidebar.title("StockAlert Dashboard")

# Navigation
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "",
    ["📊 Dashboard", "🔍 Ticker Validation", "🛠️ Data Correction"]
)

# Convert page names to match the expected values in the code
page_mapping = {
    "📊 Dashboard": "Dashboard",
    "🔍 Ticker Validation": "Ticker Validation",
    "🛠️ Data Correction": "Data Correction"
}
page = page_mapping[page]

# Title
st.markdown('<div class="dashboard-title">📈 StockAlert Dashboard</div>', unsafe_allow_html=True)

if page == "Dashboard":
    # Select category
    category = st.sidebar.selectbox(
        "Select Asset Category",
        ["All", "ideas", "digitalassets", "etfs", "daily"]
    )

    # Select sentiment
    sentiment = st.sidebar.selectbox(
        "Select Sentiment",
        ["All", "BULLISH", "BEARISH", "NEUTRAL"]
    )

    # Refresh button
    if st.sidebar.button("Refresh Data"):
        st.sidebar.success("Data refreshed!")

    # Main content
    # Get data from database
    category_filter = None if category == "All" else category
    
    # Get data based on filters
    if category == "All":
        df = db_manager.get_asset_data()
    else:
        df = db_manager.get_asset_data(category=category)
    
    # Convert to DataFrame
    if df:
        df = pd.DataFrame(df)
        
        # Format DataFrame
        if 'current_price' in df.columns:
            df['current_price'] = df['current_price'].astype(float).round(2)
        if 'buy_trade' in df.columns:
            df['buy_trade'] = df['buy_trade'].astype(float).round(2)
        if 'sell_trade' in df.columns:
            df['sell_trade'] = df['sell_trade'].astype(float).round(2)
        
        # Add emoji and color for sentiment
        if 'sentiment' in df.columns:
            df['sentiment_display'] = df['sentiment'].apply(lambda x: 
                f'<span class="bullish">🔼 {x}</span>' if x == 'BULLISH' else 
                (f'<span class="bearish">🔽 {x}</span>' if x == 'BEARISH' else 
                 f'<span class="neutral">➡️ {x}</span>'))
        
        # Create a filtered version for display
        filtered_data = df.copy()
        
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
        
        # Replace the sentiment column with the styled version for display
        if 'sentiment' in filtered_data.columns and 'sentiment_display' in filtered_data.columns:
            filtered_data['sentiment'] = filtered_data['sentiment_display']
            filtered_data = filtered_data.drop(columns=['sentiment_display'])
        
        # Display data table
        st.dataframe(filtered_data)
        
        # Manual Alert Trigger
        st.markdown('<div class="section-header"><h2>🚨 Alert System</h2></div>', unsafe_allow_html=True)
        if st.button("📧 Generate and Send Alerts Now"):
            try:
                from stockalert.scripts.alert_system import AlertSystemImproved
                
                with st.spinner("Generating and sending alerts..."):
                    alert_system = AlertSystemImproved()
                    alerts = alert_system.run()
                    
                    if alerts:
                        st.success(f"✅ Successfully generated and sent {len(alerts)} alerts!")
                        
                        # Display the alerts that were sent
                        st.subheader("📬 Alerts Sent")
                        
                        # Check if a fallback HTML file was created
                        import glob
                        from datetime import datetime
                        import re
                        
                        # Get the most recent email alert HTML file
                        html_files = glob.glob(str(Path(__file__).parent / 'data' / 'email_alerts_*.html'))
                        if html_files:
                            latest_file = max(html_files, key=os.path.getctime)
                            
                            # Read the HTML content
                            with open(latest_file, 'r') as f:
                                html_content = f.read()
                            
                            # Parse the HTML to extract alert data
                            # Extract the timestamp from the HTML
                            timestamp_match = re.search(r'<h2>Stock Alerts \((.*?)\)</h2>', html_content)
                            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                            
                            # Extract alert data using regex
                            alert_pattern = re.compile(r'(\d+)\. ([\w\^=\-\.]+) \((.*?)\) at (\$?[\d\.]+) -> ([\w\s]+) \((\$?[\d\.]+)-(\$?[\d\.]+) ([\w]+)\) for ([+-]?[\d\.]+)% ([\w]+)')
                            alerts_data = []
                            
                            for match in alert_pattern.finditer(html_content):
                                num, ticker, name, current_price, action, buy_price, sell_price, sentiment, profit_pct, profit_type = match.groups()
                                
                                # Remove $ sign if present
                                current_price = current_price.replace('$', '')
                                buy_price = buy_price.replace('$', '')
                                sell_price = sell_price.replace('$', '')
                                
                                alerts_data.append({
                                    "ticker": ticker,
                                    "name": name,
                                    "sentiment": sentiment,
                                    "category": re.search(r'<h3>(.*?)</h3>', html_content[:match.start()]).group(1) if re.search(r'<h3>(.*?)</h3>', html_content[:match.start()]) else "Unknown",
                                    "current_price": float(current_price),
                                    "buy_trade": float(buy_price),
                                    "sell_trade": float(sell_price),
                                    "action": action
                                })
                            
                            # Create a DataFrame from the parsed data
                            if alerts_data:
                                alerts_table = pd.DataFrame(alerts_data)
                                
                                # Verify category data integrity by cross-checking with database
                                try:
                                    conn = sqlite3.connect(str(Path(__file__).parent / 'data' / 'stocks.db'))
                                    cursor = conn.cursor()
                                    
                                    for i, row in alerts_table.iterrows():
                                        ticker = row['ticker']
                                        cursor.execute("SELECT category FROM stocks WHERE ticker = ?", (ticker,))
                                        result = cursor.fetchone()
                                        if result:
                                            # Update category with the one from database for accuracy
                                            alerts_table.at[i, 'category'] = result[0]
                                    
                                    conn.close()
                                except Exception as e:
                                    st.warning(f"Could not verify categories from database: {e}")
                                
                                # Display the styled table
                                st.write(f"Generated on: {timestamp}")
                                st.dataframe(alerts_table, use_container_width=True)
                            else:
                                st.info("No alerts found in the email content")
                        else:
                            # If no HTML file is found, display the original alert dataframe
                            alert_df = pd.DataFrame(alerts)
                            st.dataframe(alert_df)
                    else:
                        st.info("ℹ️ No alerts generated based on current data and thresholds")
            except Exception as e:
                st.error(f"❌ Error generating alerts: {str(e)}")
        
        # Calculate price vs range
        if 'current_price' in df.columns and 'buy_trade' in df.columns and 'sell_trade' in df.columns:
            df['price_vs_buy'] = ((df['current_price'] - df['buy_trade']) / df['buy_trade'] * 100).round(2)
            df['price_vs_sell'] = ((df['current_price'] - df['sell_trade']) / df['sell_trade'] * 100).round(2)
            
            # Create visualization
            st.subheader("Price vs Trade Range")
            
            # Select visualization type
            viz_type = st.selectbox(
                "Select Visualization",
                ["Bar Chart", "Scatter Plot"]
            )
            
            if viz_type == "Bar Chart":
                fig = px.bar(
                    df,
                    x="ticker",
                    y=["price_vs_buy", "price_vs_sell"],
                    title="Price vs Trade Range (%)",
                    barmode="group",
                    color_discrete_sequence=["green", "red"]
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                fig = px.scatter(
                    df,
                    x="buy_trade",
                    y="sell_trade",
                    size="current_price",
                    color="category",
                    hover_name="ticker",
                    title="Buy vs Sell Trade Prices"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Opportunities section
            st.markdown('<div class="section-header"><h2>💰 Opportunities</h2></div>', unsafe_allow_html=True)
            
            # Create a tab for each type of opportunity
            opportunity_tabs = st.tabs(["🔼 Buy", "🔽 Sell", "↗️ Cover", "↘️ Short"])
            
            # Process opportunities using the same logic as the alert system
            opportunities = []
            for _, row in df.iterrows():
                current_price = row['current_price']
                buy_trade = row['buy_trade']
                sell_trade = row['sell_trade']
                sentiment = row['sentiment'].upper()
                
                opportunity = {
                    'ticker': row['ticker'],
                    'name': row['name'],
                    'category': row['category'],
                    'sentiment': sentiment,
                    'current_price': current_price,
                    'buy_trade': buy_trade,
                    'sell_trade': sell_trade,
                    'action': None
                }
                
                # Use the same logic as in alert_system.py
                if sentiment == 'BULLISH':
                    if current_price >= sell_trade * 0.98:  # Within 2% of sell target
                        opportunity.update({
                            'action': 'Sell'
                        })
                    elif current_price <= buy_trade * 1.02:  # Within 2% of buy target
                        opportunity.update({
                            'action': 'Buy'
                        })
                elif sentiment == 'BEARISH':
                    if current_price <= buy_trade:  # Price is below buy price
                        opportunity.update({
                            'action': 'Cover'
                        })
                    elif current_price >= sell_trade * 0.98:  # Within 2% of sell target
                        opportunity.update({
                            'action': 'Short'
                        })
                
                if opportunity['action'] is not None:
                    opportunities.append(opportunity)
            
            # Group opportunities by action
            buy_opportunities = [o for o in opportunities if o['action'] == 'Buy']
            sell_opportunities = [o for o in opportunities if o['action'] == 'Sell']
            cover_opportunities = [o for o in opportunities if o['action'] == 'Cover']
            short_opportunities = [o for o in opportunities if o['action'] == 'Short']
            
            # Display opportunities in tabs
            with opportunity_tabs[0]:  # Buy tab
                if buy_opportunities:
                    buy_df = pd.DataFrame(buy_opportunities)
                    st.markdown(f"<h3 class='bullish'>✅ Found {len(buy_opportunities)} potential Buy opportunities</h3>", unsafe_allow_html=True)
                    
                    # Display each opportunity as a card
                    for i, row in buy_df.iterrows():
                        current_price_display = format_price(row['current_price'], row['ticker'], row['category'])
                        target_price_display = format_price(row['buy_trade'], row['ticker'], row['category'])
                        st.markdown(f"""
                        <div class="highlight">
                            <h4>{row['ticker']} - {row['name']}</h4>
                            <p>Current: <b>{current_price_display}</b> | Target: <b>{target_price_display}</b></p>
                            <p>Category: {row['category']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No Buy opportunities found")
            
            with opportunity_tabs[1]:  # Sell tab
                if sell_opportunities:
                    sell_df = pd.DataFrame(sell_opportunities)
                    st.markdown(f"<h3 class='bearish'>✅ Found {len(sell_opportunities)} potential Sell opportunities</h3>", unsafe_allow_html=True)
                    
                    # Display each opportunity as a card
                    for i, row in sell_df.iterrows():
                        current_price_display = format_price(row['current_price'], row['ticker'], row['category'])
                        target_price_display = format_price(row['sell_trade'], row['ticker'], row['category'])
                        st.markdown(f"""
                        <div class="highlight">
                            <h4>{row['ticker']} - {row['name']}</h4>
                            <p>Current: <b>{current_price_display}</b> | Target: <b>{target_price_display}</b></p>
                            <p>Category: {row['category']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No Sell opportunities found")
            
            with opportunity_tabs[2]:  # Cover tab
                if cover_opportunities:
                    cover_df = pd.DataFrame(cover_opportunities)
                    st.markdown(f"<h3 class='bullish'>✅ Found {len(cover_opportunities)} potential Cover opportunities</h3>", unsafe_allow_html=True)
                    
                    # Display each opportunity as a card
                    for i, row in cover_df.iterrows():
                        current_price_display = format_price(row['current_price'], row['ticker'], row['category'])
                        target_price_display = format_price(row['buy_trade'], row['ticker'], row['category'])
                        st.markdown(f"""
                        <div class="highlight">
                            <h4>{row['ticker']} - {row['name']}</h4>
                            <p>Current: <b>{current_price_display}</b> | Target: <b>{target_price_display}</b></p>
                            <p>Category: {row['category']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No Cover opportunities found")
            
            with opportunity_tabs[3]:  # Short tab
                if short_opportunities:
                    short_df = pd.DataFrame(short_opportunities)
                    st.markdown(f"<h3 class='bearish'>✅ Found {len(short_opportunities)} potential Short opportunities</h3>", unsafe_allow_html=True)
                    
                    # Display each opportunity as a card
                    for i, row in short_df.iterrows():
                        current_price_display = format_price(row['current_price'], row['ticker'], row['category'])
                        target_price_display = format_price(row['sell_trade'], row['ticker'], row['category'])
                        st.markdown(f"""
                        <div class="highlight">
                            <h4>{row['ticker']} - {row['name']}</h4>
                            <p>Current: <b>{current_price_display}</b> | Target: <b>{target_price_display}</b></p>
                            <p>Category: {row['category']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No Short opportunities found")
    else:
        st.info("No data found for the selected filters")

elif page == "Ticker Validation":
    st.title("Ticker Validation")
    
    # Get validation errors
    validation_errors = db_manager.get_validation_errors()
    
    if isinstance(validation_errors, list):
        if validation_errors:
            st.warning(f"Found {len(validation_errors)} tickers that need validation")
            
            # Create a DataFrame for display
            df_errors = pd.DataFrame(validation_errors)
            st.dataframe(df_errors)
            
            # Ticker correction form
            st.subheader("Correct Ticker Symbol")
            
            col1, col2 = st.columns(2)
            
            with col1:
                original_ticker = st.selectbox(
                    "Select Ticker to Correct",
                    [error['ticker'] for error in validation_errors]
                )
                
                # Get the category for the selected ticker
                category = next((error['category'] for error in validation_errors if error['ticker'] == original_ticker), None)
                
                st.text(f"Category: {category}")
            
            with col2:
                corrected_ticker = st.text_input("Corrected Ticker Symbol")
            
            if st.button("Update Ticker"):
                if original_ticker and corrected_ticker:
                    result = db_manager.update_ticker_mapping(original_ticker, corrected_ticker, category)
                    
                    if result['success']:
                        st.success(f"Updated ticker: {original_ticker} → {corrected_ticker}")
                        # Refresh the page to show updated list
                        st.experimental_rerun()
                    else:
                        st.error(f"Error: {result['error']}")
                else:
                    st.warning("Please select a ticker and enter a corrected symbol")
        else:
            st.success("No ticker validation issues found!")
    else:
        st.error(f"Error retrieving validation errors: {validation_errors['error']}")

elif page == "Data Correction":
    st.title("Data Correction")
    
    # Data correction form
    correction_ticker = st.text_input("Ticker Symbol")
    correction_category = st.selectbox(
        "Category",
        ["ideas", "digitalassets", "etfs", "daily"]
    )
    correction_field = st.selectbox(
        "Field to Correct",
        ["ticker", "name", "sentiment", "buy_trade", "sell_trade"]
    )
    correction_value = st.text_input("Corrected Value")

    if st.button("Apply Correction"):
        if correction_ticker and correction_value:
            result = db_manager.add_correction(
                correction_ticker, 
                correction_category, 
                correction_field, 
                correction_value
            )
            if result['success']:
                st.success(f"Correction applied: {correction_field} changed from {result['original_value']} to {result['corrected_value']}")
            else:
                st.error(f"Error: {result['error']}")
        else:
            st.warning("Please enter ticker and corrected value")
