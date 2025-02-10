import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import numpy as np

# Add auto refresh
def auto_refresh():
    """Auto refresh yfinance data every 3 minutes"""
    if 'last_refresh' not in st.session_state:
        st.session_state['last_refresh'] = datetime.now()
        st.session_state['db_data'] = None  # Store DB data once

    time_since_refresh = datetime.now() - st.session_state['last_refresh']
    minutes, seconds = divmod((180 - time_since_refresh.seconds), 60)
    st.sidebar.markdown(f"Next refresh in: **{minutes:02d}:{seconds:02d}**")

    if time_since_refresh.seconds >= 180:
        st.session_state['last_refresh'] = datetime.now()
        st.rerun()

# Add scripts to path
sys.path.append(str(Path(__file__).parent.parent))
from scripts.alert_system import AlertSystem

# Page config
st.set_page_config(
    page_title="Actionable Signals",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {font-size:28px; font-weight:bold; margin-bottom:0px;}
    .sub-header {font-size:14px; color:#666666; margin-top:0px;}
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stButton > button {width: 100%;}
    </style>
""", unsafe_allow_html=True)

def color_percentage(val):
    """Color coding for trade percentages"""
    if pd.isna(val):
        return ''
    if abs(val) < 1:
        return 'background-color: #FFEB9C'  # yellow for close to trade
    elif val > 0:
        return f'background-color: rgba(255, 0, 0, {min(abs(val)/10, 0.8)})'
    else:
        return f'background-color: rgba(0, 255, 0, {min(abs(val)/10, 0.8)})'

def color_sentiment(val):
    """Color coding for sentiment"""
    if val == 'BULLISH':
        return 'color: green'
    elif val == 'BEARISH':
        return 'color: red'
    return ''

def color_signal(val):
    """Color coding for signals"""
    if pd.isna(val):
        return ''
    if val in ['Buy', 'Cover']:
        return 'color: green'
    elif val in ['Sell', 'Short']:
        return 'color: red'
    return ''

def create_summary_metrics(df):
    """Create summary metrics cards"""
    total_signals = len(df)
    bullish_count = len(df[df['Sentiment'] == 'BULLISH'])
    bearish_count = len(df[df['Sentiment'] == 'BEARISH'])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Signals", total_signals)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Bullish Signals", bullish_count, delta=f"{bullish_count/total_signals*100:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Bearish Signals", bearish_count, delta=f"{bearish_count/total_signals*100:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Categories", len(df['Category'].unique()))
        st.markdown('</div>', unsafe_allow_html=True)

def create_charts(df):
    """Create charts for the dashboard"""
    # Create subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Average Change % by Category', 'Signal Count by Category'),
        specs=[[{"type": "bar"}, {"type": "pie"}]]
    )

    # Bar chart - Average Change % by Category
    category_changes = df.groupby('Category', as_index=False).agg({
        'Current Price': lambda x: ((x - df.loc[x.index, 'Buy Trade']) / df.loc[x.index, 'Buy Trade'] * 100).mean()
    }).rename(columns={'Current Price': 'Change %'})

    fig.add_trace(
        go.Bar(
            x=category_changes['Category'],
            y=category_changes['Change %'],
            name='Avg Change %',
            marker_color='lightblue'
        ),
        row=1, col=1
    )

    # Pie chart - Signal Count by Category
    category_counts = df['Category'].value_counts()
    fig.add_trace(
        go.Pie(
            labels=category_counts.index,
            values=category_counts.values,
            name='Category Distribution'
        ),
        row=1, col=2
    )

    # Update layout
    fig.update_layout(
        height=400,
        showlegend=False,
        title_text="Trading Signals Analysis"
    )

    return fig

def get_ticker_data(ticker_symbol):
    """Get all required data for a ticker in one call"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist_day = ticker.history(period="1d")
        hist_year = ticker.history(period="1y")
        
        return {
            'current_price': hist_day['Close'].iloc[-1],
            'day_low': hist_day['Low'].iloc[0],
            'day_high': hist_day['High'].iloc[0],
            'year_low': hist_year['Low'].min(),
            'year_high': hist_year['High'].max()
        }
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None

def format_range(low, high):
    """Format price ranges with consistent decimal places"""
    if pd.isna(low) or pd.isna(high):
        return ''
    if max(abs(low), abs(high)) >= 1000:
        return f"{low:,.0f}-{high:,.0f}"
    return f"{low:.2f}-{high:.2f}"

def color_range(val, sentiment):
    """Color ranges based on sentiment"""
    if pd.isna(val) or val == '':
        return ''
    if sentiment == 'BULLISH':
        return 'color: #006400'  # Dark green
    elif sentiment == 'BEARISH':
        return 'color: #8B0000'  # Dark red
    return 'color: #666666'      # Gray for neutral

class Dashboard:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.alert_system = AlertSystem()
        # Initialize session state for alerts
        if 'current_alerts' not in st.session_state:
            st.session_state['current_alerts'] = None

    def get_data(self):
        """Get data from SQLite database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            query = "SELECT * FROM stocks ORDER BY Category, Ticker"
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()

    def show_detailed_signals(self, df):
        """Show detailed signals table with trading percentages"""
        # Show loading spinner while fetching data
        with st.spinner('Fetching market data...'):
            # Get current prices and ranges in one pass
            filtered_df = df.copy()
            
            def update_ticker_data(row):
                data = get_ticker_data(row['Ticker'])
                if data:
                    return pd.Series({
                        'Current Price': data['current_price'],
                        'Day Range': format_range(data['day_low'], data['day_high']),
                        'Year Range': format_range(data['year_low'], data['year_high'])
                    })
                return pd.Series({'Current Price': None, 'Day Range': '', 'Year Range': ''})

            ticker_data = filtered_df.apply(update_ticker_data, axis=1)
            filtered_df['Current Price'] = ticker_data['Current Price']
            filtered_df['Day Range'] = ticker_data['Day Range']
            filtered_df['Year Range'] = ticker_data['Year Range']

        # Calculate signals and percentages
        def calculate_signals_and_percentages(row):
            if pd.isna(row['Current Price']) or row['Sentiment'] == 'NEUTRAL':
                return pd.Series([None, None, None, None])

            current = row['Current Price']

            if row['Sentiment'] == 'BULLISH':
                open_signal, close_signal = 'Buy', 'Sell'
                open_pct = ((row['Buy Trade'] - current) / current) * 100
                close_pct = ((row['Sell Trade'] - current) / current) * 100
            else:  # BEARISH
                open_signal, close_signal = 'Cover', 'Short'
                open_pct = ((row['Buy Trade'] - current) / current) * 100
                close_pct = ((row['Sell Trade'] - current) / current) * 100
            
            return pd.Series([open_signal, open_pct, close_signal, close_pct])

        # Add signals and percentages to dataframe
        signals_df = filtered_df.apply(calculate_signals_and_percentages, axis=1)
        filtered_df['Open Signal'], filtered_df['Open %'], filtered_df['Close Signal'], filtered_df['Close %'] = signals_df[0], signals_df[1], signals_df[2], signals_df[3]

        # Create summary metrics and charts
        create_summary_metrics(filtered_df)
        st.plotly_chart(create_charts(filtered_df), use_container_width=True)
        
        st.subheader("📝 Trading Signals")
        
        # Add filters
        col1, col2 = st.columns(2)
        with col1:
            categories = ['All'] + sorted(df['Category'].unique().tolist())
            selected_category = st.selectbox('Filter by Category', categories)
        
        with col2:
            sentiments = ['All'] + sorted(df['Sentiment'].unique().tolist())
            selected_sentiment = st.selectbox('Filter by Sentiment', sentiments)

        # Apply filters after calculations
        if selected_category != 'All':
            filtered_df = filtered_df[filtered_df['Category'] == selected_category]
        if selected_sentiment != 'All':
            filtered_df = filtered_df[filtered_df['Sentiment'] == selected_sentiment]

        # Custom number formatter
        def format_number(x):
            if pd.isna(x):
                return ''
            if abs(x) >= 1000:
                return f'{x:,.0f}'
            return f'{x:,.2f}'

        # Update display columns to include ranges
        display_df = filtered_df[[
            'Sentiment', 'Category', 'Ticker', 'Name', 'Current Price',
            'Buy Trade', 'Open Signal', 'Open %', 'Sell Trade', 'Close Signal', 'Close %',
            'Day Range', 'Year Range'
        ]]

        # Display with updated formatting
        st.dataframe(
            display_df.style
            .format({
                'Buy Trade': format_number,
                'Sell Trade': format_number,
                'Current Price': format_number,
                'Open %': '{:+.1f}%',
                'Close %': '{:+.1f}%'
            })
            .map(color_percentage, subset=['Open %', 'Close %'])
            .map(color_sentiment, subset=['Sentiment'])
            .map(color_signal, subset=['Open Signal', 'Close Signal'])
            # Simpler range coloring
            .apply(lambda x: [color_range(v, x.name) for v in x], 
                   axis=0, subset=['Day Range', 'Year Range'])
            .set_table_styles([
                {'selector': 'th', 'props': [
                    ('background-color', '#f0f2f6'),
                    ('font-weight', 'bold'),
                    ('border', '2px solid #a0a0a0'),
                    ('padding', '4px')
                ]},
                {'selector': 'td', 'props': [
                    ('border', '1px solid #d0d0d0'),
                    ('padding', '4px')
                ]},
                # Column group borders
                {'selector': 'td:nth-child(4)', 'props': [('border-right', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(5)', 'props': [('border-right', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(8)', 'props': [('border-right', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(11)', 'props': [('border-right', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(13)', 'props': [('border-right', '2px solid #a0a0a0')]},
                # Center align Day Range and Year Range
                {'selector': 'td:nth-child(12)', 'props': [
                    ('text-align', 'center'),
                    ('border', '1px solid #d0d0d0')
                ]},
                {'selector': 'td:nth-child(13)', 'props': [
                    ('text-align', 'center'),
                    ('border', '1px solid #d0d0d0')
                ]},
            ]),
            hide_index=True,
            height=600,
            use_container_width=True
        )

        # Generate Alerts section at the bottom
        st.markdown("---")  # Add separator
        st.markdown("### 🔔 Generate Alerts")
        
        col1, col2 = st.columns([3,1])
        with col1:
            buffer = st.number_input("Alert Buffer (%)", 
                                   min_value=0.1, 
                                   max_value=20.0, 
                                   value=2.0, 
                                   step=0.1,
                                   key="buffer_input")
        
        with col2:
            if st.button("Generate", key="generate_button"):
                try:
                    # Get the filtered dataframe
                    df = self.alert_system.get_latest_signals()
                    if df is not None and not df.empty:
                        alerts = self.alert_system.generate_alerts(df=df, buffer_pct=buffer)
                        if alerts:
                            st.session_state['current_alerts'] = alerts
                            st.success(f"Generated {len(alerts)} alerts!")
                        else:
                            st.session_state['current_alerts'] = None
                            st.info("No alerts generated.")
                    else:
                        st.error("No data available to generate alerts.")
                except Exception as e:
                    st.session_state['current_alerts'] = None
                    st.error(f"Error generating alerts: {str(e)}")

        # Show alert preview
        if 'current_alerts' in st.session_state and st.session_state['current_alerts']:
            with st.expander("🔔 Alert Preview", expanded=True):
                alert_df = pd.DataFrame(st.session_state['current_alerts'])
                
                # Convert numeric columns to float type explicitly
                numeric_cols = ['current_price', 'open_price', 'close_price', 'open_pct', 'close_pct']
                for col in numeric_cols:
                    if col in alert_df.columns:
                        alert_df[col] = pd.to_numeric(alert_df[col], errors='coerce')
                
                # Format for display
                display_df = alert_df.copy()
                for col in numeric_cols:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "N/A")
                
                st.dataframe(display_df, use_container_width=True)
            
            if st.button("📧 Send Alerts", key="send_button"):
                try:
                    # Use original alert_df for sending (with proper numeric types)
                    self.alert_system.send_email_alert(alert_df.to_dict('records'))
                    st.success("✅ Alerts sent!")
                    st.session_state['current_alerts'] = None
                except Exception as e:
                    st.error(f"Error sending email: {str(e)}")

    def run(self):
        # Header section
        st.markdown('<p class="main-header">📈 Actionable Signals</p>', unsafe_allow_html=True)
        est = pytz.timezone('US/Eastern')
        st.markdown(
            f'<p class="sub-header">Last Updated: {datetime.now(est).strftime("%m/%d/%Y %H:%M EST")}</p>', 
            unsafe_allow_html=True
        )
        
        # Main content
        df = self.get_data()
        if not df.empty:
            self.show_detailed_signals(df)

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.run()
    auto_refresh()