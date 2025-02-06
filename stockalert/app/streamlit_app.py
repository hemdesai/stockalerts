import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta
import pytz

# Add scripts to path
sys.path.append(str(Path(__file__).parent.parent))
from scripts.alert_system import AlertSystem

# Page config
st.set_page_config(
    page_title="Actionable Signals",
    page_icon="📈",
    layout="wide"
)

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

def generate_alert_section():
    """Create alert generation section in top-right corner"""
    with st.container():
        # Create columns with most space empty, alert generator on right
        col1, col2, col3 = st.columns([6, 1.5, 2])
        
        # Skip first column (empty space)
        with col2:
            buffer = st.number_input(
                "Alert Buffer (%)", 
                min_value=0.1, 
                max_value=20.0, 
                value=2.0, 
                step=0.1,
                label_visibility="collapsed",  # Hide label
                help="Minimum % difference to trigger alerts"
            )
        
        with col3:
            # Generate Alerts button with custom styling
            if st.button("🔔 Generate", type="primary", key="generate"):
                alert_system = AlertSystem()
                alerts = alert_system.generate_alerts(buffer_pct=buffer)
                
                if alerts:
                    st.session_state['current_alerts'] = alerts
                    st.session_state['show_preview'] = True
                    st.success(f"Generated {len(alerts)} alerts!")
                else:
                    st.session_state['current_alerts'] = None
                    st.session_state['show_preview'] = False
                    st.info("No alerts generated.")

    # Show preview and email button outside the columns
    if st.session_state.get('show_preview', False) and st.session_state.get('current_alerts'):
        with st.container():
            # Show preview of alerts
            with st.expander("🔔 Alert Preview", expanded=True):
                alert_df = pd.DataFrame(st.session_state['current_alerts'])
                
                # Format the alerts dataframe to match main dashboard
                st.dataframe(
                    alert_df[[
                        'ticker', 'category', 'current_price',
                        'open_price', 'open_signal', 'open_pct',
                        'close_price', 'close_signal', 'close_pct'
                    ]].style
                    .format({
                        'current_price': '${:.2f}',
                        'open_price': '${:.2f}',
                        'close_price': '${:.2f}',
                        'open_pct': '{:+.1f}%',
                        'close_pct': '{:+.1f}%'
                    })
                    .applymap(color_signal, subset=['open_signal', 'close_signal'])
                    .applymap(color_percentage, subset=['open_pct', 'close_pct'])
                    .set_properties(**{
                        'background-color': '#ffffff',
                        'color': '#333333',
                        'border': '1px solid #e1e4e8',
                        'padding': '8px',
                        'font-size': '13px'
                    })
                    .set_table_styles([
                        {'selector': 'th', 
                         'props': [('background-color', '#f6f8fa'),
                                 ('color', '#24292e'),
                                 ('font-weight', 'bold'),
                                 ('text-align', 'left'),
                                 ('padding', '8px'),
                                 ('font-size', '13px')]},
                    ]),
                    hide_index=True,
                    use_container_width=True
                )
            
            # Send email button with better styling
            col1, col2, col3 = st.columns([3, 1, 3])
            with col2:
                if st.button("📧 Send Alerts", key="send_email", type="primary"):
                    alert_system = AlertSystem()
                    alert_system.send_email_alert(st.session_state['current_alerts'])
                    st.success("✅ Alerts sent!")
                    st.session_state['current_alerts'] = None
                    st.session_state['show_preview'] = False

def auto_refresh():
    """Auto refresh the dashboard every 5 minutes"""
    # Get the last refresh time from session state
    if 'last_refresh' not in st.session_state:
        st.session_state['last_refresh'] = datetime.now()
        
    # Calculate time since last refresh
    time_since_refresh = datetime.now() - st.session_state['last_refresh']
    
    # Update the refresh countdown in sidebar
    minutes, seconds = divmod((300 - time_since_refresh.seconds), 60)
    st.sidebar.markdown(f"Next refresh in: **{minutes:02d}:{seconds:02d}**")
    
    # Refresh every 5 minutes
    if time_since_refresh.seconds >= 300:
        st.session_state['last_refresh'] = datetime.now()
        st.rerun()

class Dashboard:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.alert_system = AlertSystem()
        
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
               
        # Add filters - only two columns now
        col1, col2 = st.columns(2)
        with col1:
            categories = ['All'] + sorted(df['Category'].unique().tolist())
            selected_category = st.selectbox('Filter by Category', categories)
        
        with col2:
            sentiments = ['All'] + sorted(df['Sentiment'].unique().tolist())
            selected_sentiment = st.selectbox('Filter by Sentiment', sentiments)

        # Apply filters
        filtered_df = df.copy()
        if selected_category != 'All':
            filtered_df = filtered_df[filtered_df['Category'] == selected_category]
        if selected_sentiment != 'All':
            filtered_df = filtered_df[filtered_df['Sentiment'] == selected_sentiment]
        
        # Get current prices
        filtered_df['Current Price'] = filtered_df['Ticker'].apply(self.alert_system.get_current_price)
        
        # Calculate both signals and percentages
        def calculate_signals_and_percentages(row):
            if pd.isna(row['Current Price']) or row['Sentiment'] == 'NEUTRAL':
                return pd.Series([None, None, None, None])
            
            current = row['Current Price']
            
            if row['Sentiment'] == 'BULLISH':
                open_signal = 'Buy'
                close_signal = 'Sell'
                open_pct = ((row['Buy Trade'] - current) / current) * 100
                close_pct = ((row['Sell Trade'] - current) / current) * 100
            else:  # BEARISH
                open_signal = 'Cover'
                close_signal = 'Short'
                open_pct = ((row['Buy Trade'] - current) / current) * 100
                close_pct = ((row['Sell Trade'] - current) / current) * 100
            
            return pd.Series([open_signal, open_pct, close_signal, close_pct])
        
        # Add the new columns
        signals_df = filtered_df.apply(calculate_signals_and_percentages, axis=1)
        filtered_df['Open Signal'] = signals_df[0]
        filtered_df['Open %'] = signals_df[1]
        filtered_df['Close Signal'] = signals_df[2]
        filtered_df['Close %'] = signals_df[3]
        
        # Reorder columns with logical grouping
        display_df = filtered_df[[
            'Sentiment',      # Core info
            'Category',
            'Ticker', 
            'Name',
            'Current Price',  # Current price
            'Buy Trade',      # Open position group
            'Open Signal',    
            'Open %',
            'Sell Trade',     # Close position group
            'Close Signal',   
            'Close %'
        ]].rename(columns={
            'Buy Trade': 'Open Price',
            'Sell Trade': 'Close Price'
        })
        
        # Custom number formatter
        def format_number(x):
            if pd.isna(x):
                return ''
            if x >= 1000:
                return f'{x:,.0f}'  # No decimals for numbers >= 1000
            return f'{x:,.2f}'      # 2 decimals for numbers < 1000
        
        # Display with formatting and enhanced styling
        st.dataframe(
            display_df.style
            .format({
                'Open Price': format_number,
                'Close Price': format_number,
                'Current Price': format_number,
                'Open %': '{:+.1f}%',
                'Close %': '{:+.1f}%'
            })
            .applymap(color_percentage, subset=['Open %', 'Close %'])
            .applymap(color_sentiment, subset=['Sentiment'])
            .applymap(color_signal, subset=['Open Signal', 'Close Signal'])
            .set_table_styles([
                # Headers
                {'selector': 'th', 
                 'props': [('background-color', '#f0f2f6'), 
                          ('font-weight', 'bold'),
                          ('border', '2px solid #a0a0a0'),
                          ('padding', '8px')]},
                # All cells base style
                {'selector': 'td', 
                 'props': [('border', '1px solid #d0d0d0'),
                          ('padding', '8px')]},
                # Core info group (end at Name)
                {'selector': 'td:nth-child(4)', 
                 'props': [('border-right', '2px solid #a0a0a0')]},
                # Current Price group
                {'selector': 'td:nth-child(5)', 
                 'props': [('border-left', '2px solid #a0a0a0'),
                          ('border-right', '2px solid #a0a0a0')]},
                # Open group
                {'selector': 'td:nth-child(6)', 
                 'props': [('border-left', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(8)', 
                 'props': [('border-right', '2px solid #a0a0a0')]},
                # Close group
                {'selector': 'td:nth-child(9)', 
                 'props': [('border-left', '2px solid #a0a0a0')]},
                {'selector': 'td:nth-child(11)', 
                 'props': [('border-right', '2px solid #a0a0a0')]},
                # Table container style for scrollbar
                {'selector': '', 
                 'props': [('max-height', '600px'),
                          ('overflow-y', 'scroll'),
                          ('display', 'block'),
                          ('border-right', '8px solid #f0f2f6')]}  # Visible scrollbar track
            ]),
            hide_index=True,
            height=800,
            use_container_width=True
        )

    def run(self):
        """Run the dashboard"""
        # Initialize session state for alerts if not exists
        if 'current_alerts' not in st.session_state:
            st.session_state['current_alerts'] = None
        if 'show_preview' not in st.session_state:
            st.session_state['show_preview'] = False

        # Custom CSS for styling
        st.markdown("""
            <style>
            .main-title {
                font-size: 24px;
                font-weight: 750;
                margin-bottom: 0px;
            }
            .last-updated {
                font-size: 12px;
                color: #666;
                margin-top: 0px;
            }
            .stButton > button {
                width: 100%;
            }
            </style>
        """, unsafe_allow_html=True)

        # Header with title and last updated
        col1, col2 = st.columns([3,1])
        with col1:
            st.markdown('<p class="main-title">📈 Actionable Signals</p>', unsafe_allow_html=True)
            est = pytz.timezone('US/Eastern')
            last_updated = datetime.now(est).strftime("%m/%d/%Y %H:%M EST")
            st.markdown(f'<p class="last-updated">Last Updated: {last_updated}</p>', unsafe_allow_html=True)

        with col2:
            # Add alert generator in the top right
            generate_alert_section()

        # Add auto-refresh
        auto_refresh()

        # Get and display signals
        df = self.get_data()
        if df is not None and not df.empty:
            self.show_detailed_signals(df)

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.run()