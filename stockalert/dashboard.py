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

# Use the centralized environment loader
from stockalert.utils.env_loader import get_env, load_environment

# Remove redundant environment loading since we're using the centralized loader
# load_environment()

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from scripts.db_manager import StockAlertDBManager

# Initialize the database manager
db_manager = StockAlertDBManager()

# Set page config
st.set_page_config(
    page_title="StockAlert Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
st.sidebar.title("StockAlert Dashboard")

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Ticker Validation", "Data Correction", "Email Settings"]
)

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
    st.title("StockAlert Dashboard")

    # Get data from database
    category_filter = None if category == "All" else category
    sentiment_filter = None if sentiment == "All" else sentiment
    data = db_manager.get_asset_data(category_filter, sentiment_filter)

    if isinstance(data, list):
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Display data
            st.subheader("Asset Data")
            st.dataframe(df)
            
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
                
                # Opportunities section (renamed from Alert Opportunities)
                st.subheader("Opportunities (Profit %)")
                
                # Create a tab for each type of opportunity
                opportunity_tabs = st.tabs(["Buy", "Sell", "Cover", "Short"])
                
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
                        'action': None,
                        'profit': None
                    }
                    
                    # Use the same logic as in alert_system.py
                    if sentiment == 'BULLISH':
                        if current_price >= sell_trade * 0.98:  # Within 2% of sell target
                            profit = ((current_price - buy_trade) / buy_trade) * 100
                            opportunity.update({
                                'action': 'Sell',
                                'profit': profit
                            })
                        elif current_price <= buy_trade * 1.02:  # Within 2% of buy target
                            profit = ((buy_trade - current_price) / current_price) * 100
                            opportunity.update({
                                'action': 'Buy',
                                'profit': profit
                            })
                    elif sentiment == 'BEARISH':
                        if current_price <= buy_trade * 1.02:  # Within 2% of buy target
                            profit = ((sell_trade - current_price) / current_price) * 100
                            opportunity.update({
                                'action': 'Cover',
                                'profit': profit
                            })
                        elif current_price >= sell_trade * 0.98:  # Within 2% of sell target
                            profit = ((current_price - buy_trade) / buy_trade) * 100
                            opportunity.update({
                                'action': 'Short',
                                'profit': profit
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
                        buy_df['profit'] = buy_df['profit'].round(2)
                        st.success(f"Found {len(buy_opportunities)} potential Buy opportunities")
                        buy_df['profit'] = buy_df['profit'].apply(lambda x: f"{x}%")
                        st.dataframe(buy_df[['ticker', 'name', 'category', 'current_price', 'buy_trade', 'profit']])
                    else:
                        st.info("No Buy opportunities found")
                
                with opportunity_tabs[1]:  # Sell tab
                    if sell_opportunities:
                        sell_df = pd.DataFrame(sell_opportunities)
                        sell_df['profit'] = sell_df['profit'].round(2)
                        st.warning(f"Found {len(sell_opportunities)} potential Sell opportunities")
                        sell_df['profit'] = sell_df['profit'].apply(lambda x: f"{x}%")
                        st.dataframe(sell_df[['ticker', 'name', 'category', 'current_price', 'sell_trade', 'profit']])
                    else:
                        st.info("No Sell opportunities found")
                
                with opportunity_tabs[2]:  # Cover tab
                    if cover_opportunities:
                        cover_df = pd.DataFrame(cover_opportunities)
                        cover_df['profit'] = cover_df['profit'].round(2)
                        st.success(f"Found {len(cover_opportunities)} potential Cover opportunities")
                        cover_df['profit'] = cover_df['profit'].apply(lambda x: f"{x}%")
                        st.dataframe(cover_df[['ticker', 'name', 'category', 'current_price', 'buy_trade', 'profit']])
                    else:
                        st.info("No Cover opportunities found")
                
                with opportunity_tabs[3]:  # Short tab
                    if short_opportunities:
                        short_df = pd.DataFrame(short_opportunities)
                        short_df['profit'] = short_df['profit'].round(2)
                        st.warning(f"Found {len(short_opportunities)} potential Short opportunities")
                        short_df['profit'] = short_df['profit'].apply(lambda x: f"{x}%")
                        st.dataframe(short_df[['ticker', 'name', 'category', 'current_price', 'sell_trade', 'profit']])
                    else:
                        st.info("No Short opportunities found")
        else:
            st.info("No data found for the selected filters")
    else:
        st.error(f"Error retrieving data: {data['error']}")

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

elif page == "Email Settings":
    st.title("Email Alert Settings")
    
    # Load current settings from environment variables
    email_sender = get_env('EMAIL_SENDER')
    email_password = get_env('EMAIL_PASSWORD')
    email_recipient = get_env('EMAIL_RECIPIENT')
    
    with st.form("email_settings_form"):
        st.subheader("Email Configuration")
        
        new_email_sender = st.text_input("Sender Email (Gmail)", value=email_sender)
        st.caption("This should be a Gmail account that will send the alerts")
        
        new_email_password = st.text_input("App Password", value=email_password, type="password")
        st.caption("Use an App Password from your Google Account (not your regular password)")
        st.markdown("[How to create an App Password](https://support.google.com/accounts/answer/185833)")
        
        new_email_recipient = st.text_input("Recipient Email", value=email_recipient)
        st.caption("Email address that will receive the alerts")
        
        # Test email section
        st.subheader("Test Email")
        send_test = st.checkbox("Send a test email when saving")
        
        # Submit button
        submitted = st.form_submit_button("Save Settings")
        
        if submitted:
            # Save email settings
            def save_email_settings():
                """Save email settings to environment variables"""
                try:
                    # Get values from session state
                    email_sender = st.session_state.email_sender
                    email_password = st.session_state.email_password
                    email_recipient = st.session_state.email_recipient
                    
                    # Update environment variables
                    os.environ['EMAIL_SENDER'] = email_sender
                    os.environ['EMAIL_PASSWORD'] = email_password
                    os.environ['EMAIL_RECIPIENT'] = email_recipient
                    
                    # Reload environment variables
                    load_environment()
                    
                    st.success("Email settings saved successfully!")
                except Exception as e:
                    st.error(f"Error saving email settings: {e}")
            
            save_email_settings()
            
            # Send test email if requested
            if send_test and new_email_sender and new_email_password and new_email_recipient:
                try:
                    # Import here to avoid circular imports
                    sys.path.append(str(project_root / 'scripts'))
                    from alert_system import AlertSystem
                    
                    # Create a test alert
                    test_alert = [{
                        'ticker': 'TEST',
                        'category': 'Test Category',
                        'sentiment': 'BULLISH',
                        'name': 'Test Stock',
                        'current_price': 100.00,
                        'buy_trade': 95.00,
                        'sell_trade': 105.00,
                        'action': 'Buy',
                        'profit': 5.0
                    }]
                    
                    # Send test email
                    alert_system = AlertSystem()
                    alert_system.send_email_alert(test_alert)
                    
                    st.success("Test email sent successfully!")
                except Exception as e:
                    st.error(f"Error sending test email: {str(e)}")
    
    # Manual alert trigger section
    st.subheader("Manual Alert Trigger")
    
    if st.button("Generate and Send Alerts Now"):
        try:
            # Import here to avoid circular imports
            sys.path.append(str(project_root / 'scripts'))
            from alert_system import AlertSystem
            
            with st.spinner("Generating alerts..."):
                alert_system = AlertSystem()
                alerts = alert_system.generate_alerts()
                
                if alerts:
                    alert_system.send_email_alert(alerts)
                    st.success(f"Generated and sent {len(alerts)} alerts!")
                else:
                    st.info("No alerts generated based on current data")
        except Exception as e:
            st.error(f"Error generating alerts: {str(e)}")
    
    # Alert scheduler status
    st.subheader("Alert Scheduler Status")
    
    # Check if scheduler log exists
    scheduler_log_path = project_root / 'data' / 'scheduler.log'
    if scheduler_log_path.exists():
        with open(scheduler_log_path, 'r') as f:
            log_content = f.readlines()
            # Show last 10 lines
            st.code(''.join(log_content[-10:]), language="bash")
    else:
        st.info("No scheduler log found. The scheduler may not be running yet.")
    
    # Instructions for setting up the scheduler
    st.subheader("Scheduler Setup")
    st.markdown("""
    To set up the alert scheduler to run automatically:
    
    1. Make sure your email settings are configured correctly
    2. Run the scheduler script:
    ```bash
    python scripts/alert_scheduler.py
    ```
    3. For automatic startup, you can use the Windows Task Scheduler or create a service
    """)
