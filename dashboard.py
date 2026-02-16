"""
Praeto Tender Tracker - Streamlit Dashboard
Version: 1.0

Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import os

# ============== PAGE CONFIG ==============

st.set_page_config(
    page_title="Praeto Tender Tracker",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============== CUSTOM CSS ==============

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #003366;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #003366 0%, #0066cc 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #003366;
    }
    .urgent {
        background: #ffebee;
        border-left-color: #d32f2f;
    }
    .warning {
        background: #fff3e0;
        border-left-color: #f57c00;
    }
    .success {
        background: #e8f5e9;
        border-left-color: #388e3c;
    }
    .stDataFrame {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ============== GOOGLE SHEETS CONNECTION ==============

@st.cache_resource
def get_google_sheet():
    """Connect to Google Sheets"""
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # For deployment: use secrets
        # For local: use service_account.json
        if os.path.exists('service_account.json'):
            creds = Credentials.from_service_account_file('service_account.json', scopes=scope)
        else:
            # Streamlit Cloud secrets
            import json
            try:
                creds_dict = st.secrets["gcp_service_account"]
                creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            except:
                st.warning("Service account credentials not found. Please follow the setup guide.")
                return None
        
        client = gspread.authorize(creds)
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1pHXkYhOyXrKsHP7syDK_WfQh3xy-Qn-hHdJLNlV0mbg/edit")
        return sheet
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load tender data from Google Sheets"""
    sheet = get_google_sheet()
    if not sheet:
        return pd.DataFrame()
    
    try:
        worksheet = sheet.worksheet('Raw_Data')
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Data cleaning
        if not df.empty:
            df['Closing_Date'] = pd.to_datetime(df['Closing_Date'], errors='coerce')
            df['Days_Remaining'] = pd.to_numeric(df['Days_Remaining'], errors='coerce')
            df['Value_ZAR'] = pd.to_numeric(df['Value_ZAR'], errors='coerce').fillna(0)
            
            # Calculate urgency
            df['Urgency'] = df['Days_Remaining'].apply(
                lambda x: '🔴 Critical (< 7 days)' if x < 7 
                else '🟡 Urgent (7-30 days)' if x < 30 
                else '🟢 Normal (> 30 days)' if x >= 0 
                else '⚫ Expired'
            )
            
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# ============== SIDEBAR ==============

def render_sidebar():
    """Render filter sidebar"""
    st.sidebar.markdown("## 🎛️ Filters")
    
    df = load_data()
    
    if df.empty:
        st.sidebar.warning("No data loaded")
        return None
    
    # Category filter
    categories = ['All'] + sorted(df['Category'].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("Category", categories)
    
    # Source filter
    sources = ['All'] + sorted(df['Source'].dropna().unique().tolist())
    selected_source = st.sidebar.selectbox("Source", sources)
    
    # Priority buyer filter
    priority_buyers = ['All', 'Yes', 'No']
    selected_priority = st.sidebar.selectbox("Priority Buyer", priority_buyers)
    
    # Urgency filter
    urgencies = ['All', '🔴 Critical (< 7 days)', '🟡 Urgent (7-30 days)', 
                '🟢 Normal (> 30 days)', '⚫ Expired']
    selected_urgency = st.sidebar.selectbox("Urgency", urgencies)
    
    # Days remaining slider
    max_days = int(df['Days_Remaining'].max()) if not df.empty else 365
    day_range = st.sidebar.slider("Days Remaining", 0, max_days, (0, max_days))
    
    # Search
    search_term = st.sidebar.text_input("🔍 Search tenders...")
    
    # Apply filters
    filtered = df.copy()
    
    if selected_category != 'All':
        filtered = filtered[filtered['Category'] == selected_category]
    
    if selected_source != 'All':
        filtered = filtered[filtered['Source'] == selected_source]
    
    if selected_priority != 'All':
        filtered = filtered[filtered['Priority_Buyer'] == selected_priority]
    
    if selected_urgency != 'All':
        filtered = filtered[filtered['Urgency'] == selected_urgency]
    
    filtered = filtered[
        (filtered['Days_Remaining'] >= day_range[0]) & 
        (filtered['Days_Remaining'] <= day_range[1])
    ]
    
    if search_term:
        mask = (
            filtered['Title'].str.contains(search_term, case=False, na=False) |
            filtered['Buyer'].str.contains(search_term, case=False, na=False) |
            filtered['Description'].str.contains(search_term, case=False, na=False)
        )
        filtered = filtered[mask]
    
    # Quick stats in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📊 Quick Stats")
    st.sidebar.metric("Total Tenders", len(df))
    st.sidebar.metric("Filtered Results", len(filtered))
    if not df.empty:
        st.sidebar.metric("Critical (< 7 days)", len(df[df['Days_Remaining'] < 7]))
    
    return filtered

# ============== MAIN DASHBOARD ==============

def render_metrics(df):
    """Render top metric cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_value = df['Value_ZAR'].sum() if not df.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>💰 Total Value</h3>
            <h2>R{total_value:,.0f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        active = len(df[df['Days_Remaining'] >= 0]) if not df.empty else 0
        st.markdown(f"""
        <div class="metric-card success">
            <h3>✅ Active Tenders</h3>
            <h2>{active}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        urgent = len(df[(df['Days_Remaining'] >= 0) & (df['Days_Remaining'] < 30)]) if not df.empty else 0
        st.markdown(f"""
        <div class="metric-card warning">
            <h3>⏰ Closing Soon (< 30 days)</h3>
            <h2>{urgent}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        critical = len(df[df['Days_Remaining'] < 7]) if not df.empty else 0
        st.markdown(f"""
        <div class="metric-card urgent">
            <h3>🚨 Critical (< 7 days)</h3>
            <h2>{critical}</h2>
        </div>
        """, unsafe_allow_html=True)

def render_charts(df):
    """Render visualization charts"""
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Tenders by Category")
        cat_counts = df['Category'].value_counts()
        fig = px.pie(
            values=cat_counts.values,
            names=cat_counts.index,
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📅 Tenders by Closing Month")
        df['Closing_Month'] = df['Closing_Date'].dt.to_period('M').astype(str)
        monthly = df.groupby('Closing_Month').size().reset_index(name='Count')
        
        fig = px.bar(
            monthly,
            x='Closing_Month',
            y='Count',
            color='Count',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

def render_tender_table(df):
    """Render interactive tender table"""
    st.markdown("### 📋 Tender Details")
    
    if df.empty:
        st.info("No tenders match your filters")
        return
    
    # Format for display
    display_df = df[[
        'Urgency', 'Category', 'Buyer', 'Title', 
        'Closing_Date', 'Days_Remaining', 'Value_ZAR', 
        'Source', 'Document_Link'
    ]].copy()
    
    display_df.columns = [
        'Status', 'Category', 'Buyer', 'Title',
        'Closing Date', 'Days Left', 'Value (ZAR)',
        'Source', 'Documents'
    ]
    
    # Format value
    display_df['Value (ZAR)'] = display_df['Value (ZAR)'].apply(lambda x: f"R{x:,.0f}" if x > 0 else "N/A")
    
    # Make document links clickable
    display_df['Documents'] = display_df['Documents'].apply(
        lambda x: f'<a href="{x}" target="_blank">📄 View</a>' if x else "N/A"
    )
    
    # Display with HTML
    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Export options
    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            "tenders_export.csv",
            "text/csv"
        )
    with col2:
        # Excel export
        try:
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Tenders')
            st.download_button(
                "📥 Download Excel",
                buffer.getvalue(),
                "tenders_export.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except:
            st.warning("Excel export requires 'xlsxwriter' package.")

# ============== MAIN APP ==============

def main():
    # Header
    st.markdown('<div class="main-header">🎯 PRAETO TENDER TRACKER</div>', unsafe_allow_html=True)
    
    # Load and filter data
    filtered_df = render_sidebar()
    
    if filtered_df is None:
        st.error("Unable to load data. Please check Google Sheets connection.")
        return
    
    # Metrics
    render_metrics(filtered_df)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📋 Tenders", "⚙️ Settings"])
    
    with tab1:
        render_charts(filtered_df)
        
        # Priority buyers section
        st.markdown("### ⭐ Priority Buyer Tenders")
        priority_df = filtered_df[filtered_df['Priority_Buyer'] == 'Yes']
        if not priority_df.empty:
            st.dataframe(
                priority_df[['Buyer', 'Title', 'Closing_Date', 'Days_Remaining', 'Category']],
                use_container_width=True
            )
        else:
            st.info("No priority buyer tenders match current filters")
    
    with tab2:
        render_tender_table(filtered_df)
    
    with tab3:
        st.markdown("### ⚙️ Configuration")
        st.json({
            "Sheet URL": "https://docs.google.com/spreadsheets/d/1pHXkYhOyXrKsHP7syDK_WfQh3xy-Qn-hHdJLNlV0mbg/edit",
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Categories": ["insurance", "advisory_consulting", "civil_engineering", 
                          "cleaning_facility", "construction"],
            "Team Size": 5,
            "Scraping Frequency": "Daily at 08:00 SAST"
        })
        
        # Manual refresh
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    main()
