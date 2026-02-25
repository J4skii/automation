"""
Praeto Tender Tracker - Automated Scraper
Version: 1.0
Author: Automation System
Date: 2025-02-13

DESCRIPTION:
Automated scraper for South African tender portals:
- eTenders.gov.za
- EasyTenders.co.za  
- Transnet eTenders

Categorizes tenders by: Insurance, Advisory, Civil Engineering, 
Cleaning/Facility Management, Construction

Outputs to Google Sheets and sends email alerts.
"""

import os
import json
import time
import logging
import smtplib
import requests
import gspread
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from google.oauth2.service_account import Credentials

# ============== CONFIGURATION ==============

# Google Sheets
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1pHXkYhOyXrKsHP7syDK_WfQh3xy-Qn-hHdJLNlV0mbg/edit"
SERVICE_ACCOUNT_FILE = "service_account.json"  # Download from Google Cloud Console

# Email Settings (Outlook/Office 365)
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
EMAIL_USERNAME = "jaden@praeto.co.za"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Set as environment variable
ALERT_RECIPIENTS = [
    "jaden@praeto.co.za",
    "admin1@praeto.co.za",
    "admin3@praeto.co.za",
    "jared@praeto.co.za",
    "josh@praeto.co.za"
]

# Categories and Keywords - INSURANCE ONLY
CATEGORIES = {
    "insurance": {
        "keywords": ["insurance", "broker", "risk management", "underwriting", 
                    "policy", "premium", "claim", "sasria", "fidelity", 
                    "liability", "indemnity", "surety", "bond", "actuarial", 
                    "loss control", "marine", "aviation", "motor fleet",
                    "short-term", "medical aid", "pension", "provident", "guarantee",
                    "group life", "funeral cover", "professional indemnity", 
                    "public liability", "employers liability", "property insurance",
                    "motor insurance", "asset insurance", "business interruption",
                    "cyber insurance", "directors and officers", "D&O", "surety bond",
                    "insurance broker", "reinsurance", "loss assessor", "claims handler"],
        "priority": 1
    }
}

# Priority Buyers (from your list)
PRIORITY_BUYERS = [
    "Chief Albert Luthuli Municipality",
    "Financial and Fiscal Commission",
    "CIDB",
    "National Treasury",
    "AEMFC",
    "ERWAT",
    "MQA",
    "TASEZ",
    "ARC",
    "MerSETA",
    "Mogalakwena"
]

# ============== SETUP LOGGING ==============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tender_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============== GOOGLE SHEETS INTERFACE ==============

class GoogleSheetsManager:
    def __init__(self, sheet_url, creds_file):
        self.sheet_url = sheet_url
        self.creds_file = creds_file
        self.client = None
        self.sheet = None
        self.connect()
        
    def connect(self):
        """Establish connection to Google Sheets API"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                self.creds_file, scopes=scope
            )
            self.client = gspread.authorize(creds)
            
            # Open by URL
            self.sheet = self.client.open_by_url(self.sheet_url)
            logger.info("Connected to Google Sheets successfully")
            
            # Ensure worksheets exist
            self._setup_worksheets()
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def _setup_worksheets(self):
        """Create worksheets if they don't exist"""
        required_sheets = ['Raw_Data', 'Dashboard', 'Settings', 
                          'Priority_Buyers', 'Categories']
        
        existing = [ws.title for ws in self.sheet.worksheets()]
        
        for sheet_name in required_sheets:
            if sheet_name not in existing:
                self.sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
                logger.info(f"Created worksheet: {sheet_name}")
                
                # Add headers to Raw_Data
                if sheet_name == 'Raw_Data':
                    headers = [
                        'Date_Scraped', 'Source', 'Tender_ID', 'Title', 
                        'Buyer', 'Category', 'Closing_Date', 'Days_Remaining',
                        'Value_ZAR', 'Description', 'Document_Link', 
                        'Status', 'Priority_Buyer', 'Alert_Sent'
                    ]
                    self.sheet.worksheet(sheet_name).append_row(headers)
    
    def get_existing_tender_ids(self):
        """Get list of already scraped tender IDs to avoid duplicates"""
        try:
            ws = self.sheet.worksheet('Raw_Data')
            # Get all values instead of records to be more robust
            all_values = ws.get_all_values()
            if len(all_values) <= 1:
                return set()
                
            # Assume Tender_ID is the 3rd column (index 2)
            headers = all_values[0]
            try:
                id_index = headers.index('Tender_ID')
            except ValueError:
                id_index = 2 # Best guess
                
            return set(str(row[id_index]) for row in all_values[1:] if len(row) > id_index and row[id_index])
        except Exception as e:
            logger.error(f"Error getting existing tenders: {e}")
            return set()
    
    def validate_tender_data(self, tender_data):
        """Ensure critical fields are properly formatted."""
        import re
        errors = []
        
        # Check closing_date is ISO format (YYYY-MM-DD)
        closing = tender_data.get('closing_date', '')
        if closing and not re.match(r'\d{4}-\d{2}-\d{2}', str(closing)):
            errors.append(f"Invalid date format: {closing}")
        
        # Check days_remaining is integer
        days = tender_data.get('days_remaining')
        if days is not None and not isinstance(days, int):
            try:
                tender_data['days_remaining'] = int(days)
            except (ValueError, TypeError):
                errors.append(f"Invalid days_remaining type: {type(days)}")
        
        return errors
    
    def auto_fix_tender(self, tender):
        """Attempt to fix common tender data issues."""
        import re
        
        # Fix closing_date if needed
        closing = tender.get('closing_date', '')
        if closing and not re.match(r'\d{4}-\d{2}-\d{2}', str(closing)):
            # Try to parse and normalize
            parsed = self._parse_date_flexible(closing)
            if parsed:
                tender['closing_date'] = parsed
                # Recalculate days_remaining
                from datetime import datetime
                try:
                    closing_date = datetime.strptime(parsed, '%Y-%m-%d')
                    days = (closing_date - datetime.now()).days
                    tender['days_remaining'] = max(0, days)
                except:
                    pass
        
        # Ensure days_remaining is integer
        if tender.get('days_remaining') is not None:
            try:
                tender['days_remaining'] = int(tender['days_remaining'])
            except (ValueError, TypeError):
                tender['days_remaining'] = 0
        
        return tender
    
    def _parse_date_flexible(self, date_str):
        """Try multiple formats to parse date string."""
        from datetime import datetime
        
        if not date_str:
            return None
        
        # Clean the string
        clean = str(date_str).replace('Closing:', '').strip()
        
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %B %Y', '%d %b %Y']
        for fmt in formats:
            try:
                parsed = datetime.strptime(clean, fmt)
                return parsed.strftime('%Y-%m-%d')
            except:
                continue
        
        # Try regex for "18 Mar" format
        match = re.search(r'(\d{1,2})\s+([A-Za-z]+)', clean)
        if match:
            day, month_abbr = match.groups()
            months = {
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            month_num = months.get(month_abbr.lower()[:3])
            if month_num:
                today = datetime.now()
                year = today.year
                try:
                    test_date = datetime(year, int(month_num), int(day))
                    if test_date < today:
                        year += 1
                    return f"{year}-{month_num}-{day.zfill(2)}"
                except ValueError:
                    pass
        
        return None

    def add_tenders(self, tenders_data):
        """Add multiple tenders to Raw_Data sheet in one batch"""
        if not tenders_data:
            return True
            
        try:
            ws = self.sheet.worksheet('Raw_Data')
            
            rows = []
            for tender_data in tenders_data:
                # Validate before adding
                if errors := self.validate_tender_data(tender_data):
                    logger.warning(f"Validation errors for {tender_data.get('tender_id')}: {errors}")
                    # Fix in place
                    tender_data = self.auto_fix_tender(tender_data)
                    logger.info(f"Auto-fixed tender: {tender_data.get('tender_id')}")
                
                row = [
                    tender_data.get('date_scraped', datetime.now().strftime('%Y-%m-%d')),
                    tender_data.get('source', ''),
                    tender_data.get('tender_id', ''),
                    tender_data.get('title', ''),
                    tender_data.get('buyer', ''),
                    tender_data.get('category', ''),
                    tender_data.get('closing_date', ''),
                    tender_data.get('days_remaining', ''),
                    tender_data.get('value_zar', ''),
                    tender_data.get('description', '')[:500],
                    tender_data.get('document_link', ''),
                    tender_data.get('status', 'New'),
                    'Yes' if tender_data.get('priority_buyer') else 'No',
                    'No'
                ]
                rows.append(row)
            
            # Use append_rows for batch operation
            ws.append_rows(rows)
            logger.info(f"Batch added {len(rows)} tenders to Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Error batch adding tenders: {e}")
            return False

    def update_dashboard(self, stats):
        """Update Dashboard worksheet with summary stats"""
        try:
            ws = self.sheet.worksheet('Dashboard')
            ws.clear()
            
            # Add summary
            ws.append_row(['TENDER TRACKER DASHBOARD'])
            ws.append_row(['Last Updated', datetime.now().strftime('%Y-%m-%d %H:%M')])
            ws.append_row([])
            ws.append_row(['Category', 'Count', 'Total Value (ZAR)'])
            
            for cat, data in stats.items():
                ws.append_row([cat, data['count'], data['total_value']])
                
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")

# ============== EMAIL ALERT SYSTEM ==============

class EmailAlerter:
    def __init__(self, smtp_server, smtp_port, username, password, recipients):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients
        
    def send_alert(self, tender):
        """Send email alert for new tender"""
        if not self.username or not self.password:
            logger.info(f"Skipping Python email alert for {tender['tender_id']} (no credentials). Google Sheets will handle alerts instead.")
            return False
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[TENDER ALERT] {tender['category'].upper()}: {tender['buyer'][:50]}"
            msg['From'] = self.username
            msg['To'] = ', '.join(self.recipients)
            
            # Create HTML email body
            html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .header {{ background: #003366; color: white; padding: 20px; }}
                    .content {{ padding: 20px; }}
                    .highlight {{ background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; }}
                    .footer {{ background: #f8f9fa; padding: 10px; font-size: 12px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                    .label {{ font-weight: bold; color: #003366; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>🎯 New Tender Alert - Praeto</h2>
                </div>
                <div class="content">
                    <div class="highlight">
                        <strong>Category:</strong> {tender['category'].replace('_', ' ').title()}<br>
                        <strong>Priority Buyer:</strong> {'⭐ YES' if tender['priority_buyer'] else 'No'}
                    </div>
                    <br>
                    <table>
                        <tr><td class="label">Buyer/Entity:</td><td>{tender['buyer']}</td></tr>
                        <tr><td class="label">Tender Title:</td><td>{tender['title']}</td></tr>
                        <tr><td class="label">Closing Date:</td><td>{tender['closing_date']} ({tender['days_remaining']} days remaining)</td></tr>
                        <tr><td class="label">Estimated Value:</td><td>R{tender['value_zar']:,.2f}</td></tr>
                        <tr><td class="label">Source:</td><td>{tender['source']}</td></tr>
                    </table>
                    <br>
                    <p><strong>Description:</strong><br>{tender['description'][:300]}...</p>
                    <br>
                    <p><a href="{tender['document_link']}" style="background: #003366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">📄 View Tender Documents</a></p>
                    <br>
                    <p><a href="{GOOGLE_SHEET_URL}" style="color: #003366;">View All Tenders in Dashboard</a></p>
                </div>
                <div class="footer">
                    <p>This is an automated alert from Praeto Tender Tracker.<br>
                    To modify your alert preferences, contact jaden@praeto.co.za</p>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                
            logger.info(f"Alert sent for tender: {tender['tender_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

# ============== TENDER SCRAPERS ==============

class BaseScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.driver = None

    def _init_selenium(self):
        """Initialize headless browser for JavaScript-heavy pages"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Add User-Agent to Selenium as well
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=options)
    
    def categorize_tender(self, title, description):
        """Determine category based on keywords"""
        text = f"{title} {description}".lower()
        
        for category, data in CATEGORIES.items():
            if any(keyword in text for keyword in data['keywords']):
                return category
        
        return "uncategorized"
    
    def calculate_days_remaining(self, closing_date_str):
        """Calculate days until closing"""
        try:
            # Handle EasyTenders format: "Closing 18 Mar" or "18 Mar"
            import re
            match = re.search(r'(\d{1,2})\s+([A-Za-z]+)', str(closing_date_str))
            if match:
                day, month_abbr = match.groups()
                months = {
                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                }
                month_num = months.get(month_abbr.lower()[:3])
                if month_num:
                    today = datetime.now()
                    year = today.year
                    try:
                        test_date = datetime(year, int(month_num), int(day))
                        if test_date < today:
                            year += 1
                        closing_date_str = f"{year}-{month_num}-{day.zfill(2)}"
                    except ValueError:
                        pass  # Invalid date, continue with other formats
            
            # Try multiple date formats
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %B %Y', '%d %b %Y']
            for fmt in formats:
                try:
                    closing = datetime.strptime(closing_date_str, fmt)
                    days = (closing - datetime.now()).days
                    return max(0, days)
                except:
                    continue
            return 0
        except:
            return 0
    
    def parse_easytenders_date(self, raw_date_text):
        """
        Convert EasyTenders' 'Closing 18 Mar' format to ISO date.
        Returns None if parsing fails.
        """
        if not raw_date_text:
            return None
        
        import re
        # Remove 'Closing:' prefix if present
        clean_text = raw_date_text.replace('Closing:', '').strip()
        
        # Extract date parts using regex
        match = re.search(r'(\d{1,2})\s+([A-Za-z]+)', clean_text)
        if not match:
            return clean_text  # Return original if pattern doesn't match
        
        day, month_abbr = match.groups()
        
        # Map month abbreviation to number
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
            'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month_num = months.get(month_abbr.lower()[:3])
        
        if not month_num:
            return clean_text
        
        # Determine year (current or next)
        today = datetime.now()
        year = today.year
        try:
            test_date = datetime(year, int(month_num), int(day))
            if test_date < today:
                year += 1
        except ValueError:
            return clean_text
        
        return f"{year}-{month_num}-{day.zfill(2)}"  # Returns: 2026-03-18

class ETendersScraper(BaseScraper):
    """Scraper for eTenders.gov.za using JSON API with GET request"""
    
    def __init__(self, username=None, password=None):
        super().__init__()
        self.base_url = "https://www.etenders.gov.za"
        
    def scrape(self):
        """Scrape using DataTables JSON API with insurance category filters"""
        tenders = []
        
        # Build the full URL with all query parameters (GET request, not POST)
        params = {
            'draw': 1,
            'start': 0,
            'length': 100,
            'search[value]': '',
            'search[regex]': 'false',
            'category': '41,5,81,83',  # Your insurance categories
            'department': '',
            'province': '',
            'cluster': 'undefined',
            'type': '',
            'esubmissions': '',
            'status': '1',
            'tenderNumber': '',
            'company': '',
            'supplierNumber': ''
        }
        
        # Add column definitions
        for i in range(7):
            col_data = ['', 'category', 'description', 'eSubmission', 'date_Published', 'closing_Date', 'actions'][i]
            params[f'columns[{i}][data]'] = col_data
            params[f'columns[{i}][name]'] = ''
            params[f'columns[{i}][searchable]'] = 'true'
            params[f'columns[{i}][orderable]'] = 'false' if i in [0, 2] else 'true'
            params[f'columns[{i}][search][value]'] = ''
            params[f'columns[{i}][search][regex]'] = 'false'
        
        params['order[0][column]'] = '5'
        params['order[0][dir]'] = 'asc'
        
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'{self.base_url}/Home/opportunities?id=1'
        }
        
        try:
            logger.info("Calling eTenders API with insurance categories: 41,5,81,83")
            
            # USE GET, NOT POST!
            response = requests.get(
                f"{self.base_url}/Home/TenderFilter/",
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            records_total = data.get('recordsTotal', 0)
            records_filtered = data.get('recordsFiltered', 0)
            
            logger.info(f"eTenders API: {records_filtered} tenders found")
            
            for item in data.get('data', []):
                try:
                    closing_raw = item.get('closing_Date', '')
                    closing_date = closing_raw.split('T')[0] if closing_raw else ''
                    
                    website_category = item.get('category', '')
                    title = item.get('description', '')
                    our_category = self.categorize_tender(title, website_category)
                    
                    # Only keep insurance or priority buyers
                    if our_category != 'insurance' and not any(pb.lower() in item.get('organ_of_State', '').lower() for pb in PRIORITY_BUYERS):
                        continue
                    
                    tender = {
                        'date_scraped': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'eTenders.gov.za',
                        'tender_id': f"ET-{item.get('id', '')}",
                        'title': title[:250],
                        'buyer': item.get('organ_of_State', 'Unknown'),
                        'category': our_category,
                        'closing_date': closing_date,
                        'days_remaining': self.calculate_days_remaining(closing_date),
                        'value_zar': 0,
                        'description': title,
                        'document_link': f"{self.base_url}/Home/TenderDetails?id={item.get('id', '')}",
                        'status': 'New',
                        'priority_buyer': any(pb.lower() in item.get('organ_of_State', '').lower() for pb in PRIORITY_BUYERS),
                        'alert_sent': False
                    }
                    
                    tenders.append(tender)
                    
                except Exception as e:
                    logger.warning(f"Error parsing tender: {e}")
                    continue
            
            logger.info(f"eTenders: Kept {len(tenders)} insurance/priority tenders")
            
        except Exception as e:
            logger.error(f"Error in eTenders scraper: {e}")
        
        return tenders


class EasyTendersScraper(BaseScraper):
    """Scraper for EasyTenders.co.za"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://easytenders.co.za"
        
    def scrape(self):
        """Scrape EasyTenders"""
        unique_tenders = {}
        
        try:
            # Search for each category keyword
            for category, data in CATEGORIES.items():
                for keyword in data['keywords']:  # Use ALL keywords per category
                    try:
                        search_url = f"{self.base_url}/tenders?sort=&search={requests.utils.quote(keyword)}&province=all&company=&industry=any&status=open-tenders&filter=1"
                        response = self.session.get(search_url, timeout=30)
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        tender_cards = soup.find_all('div', class_='tender')
                        
                        for card in tender_cards:
                            try:
                                # Update selectors based on sample HTML
                                title_div = card.find('div', class_='text-dark') or card.find('div', class_='font-size-14')
                                title = title_div.get_text(strip=True) if title_div else ""
                                
                                buyer_div = card.find('div', class_='text-primary')
                                buyer = buyer_div.get_text(strip=True) if buyer_div else ""
                                
                                closing_div = card.find('div', class_='closing-date')
                                closing = closing_div.get_text(strip=True).replace('Closing:', '').strip() if closing_div else ""
                                
                                link_tag = card.find('a', href=True)
                                link = link_tag['href'] if link_tag else ""
                                
                                if not title:
                                    continue
                                    
                                # Use title + buyer as unique key to deduplicate
                                unique_key = f"{title}_{buyer}".lower()
                                if unique_key in unique_tenders:
                                    continue
                                    
                                category_actual = self.categorize_tender(title, "")
                                
                                tender = {
                                    'source': 'EasyTenders',
                                    'tender_id': f"EZ-{datetime.now().year}-{hash(title) % 10000:04d}",
                                    'title': title,
                                    'buyer': buyer,
                                    'category': category_actual,
                                    'closing_date': closing,
                                    'days_remaining': self.calculate_days_remaining(closing),
                                    'value_zar': 0,
                                    'description': title,
                                    'document_link': self.base_url + link if link.startswith('/') else link,
                                    'priority_buyer': any(pb.lower() in buyer.lower() for pb in PRIORITY_BUYERS)
                                }
                                
                                unique_tenders[unique_key] = tender
                                
                            except Exception as e:
                                logger.warning(f"Error parsing EasyTenders card: {e}")
                                continue
                        
                        time.sleep(1)  # Be nice to the server
                        
                    except Exception as e:
                        logger.warning(f"Error searching EasyTenders for {keyword}: {e}")
                        continue
            
            tenders = list(unique_tenders.values())
            
        except Exception as e:
            logger.error(f"Error scraping EasyTenders: {e}")
            
        logger.info(f"Scraped {len(tenders)} unique tenders from EasyTenders")
        
        # Log category breakdown
        if tenders:
            category_counts = {}
            for t in tenders:
                cat = t.get('category', 'unknown')
                category_counts[cat] = category_counts.get(cat, 0) + 1
            logger.info(f"EasyTenders category breakdown: {category_counts}")
        
        return tenders

class TransnetScraper(BaseScraper):
    """Scraper for Transnet eTenders"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://transnetetenders.azurewebsites.net"
        
    def scrape(self):
        """Scrape Transnet advertised tenders"""
        tenders = []
        
        try:
            self._init_selenium()
            url = f"{self.base_url}/Home/AdvertisedTenders"
            self.driver.get(url)
            
            # Wait for table
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.ID, "_advertisedTenders")))
            
            # Click the 'Ads' link if necessary or ensure it's loaded
            # Sometimes we need to wait for the data to actually populate
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            table = soup.find('table', {'id': '_advertisedTenders'})
            
            if table:
                rows = table.find_all('tr')[1:] # Skip header
                
                for row in rows:
                    try:
                        cols = row.find_all('td')
                        if len(cols) < 5:
                            continue
                        
                        title = cols[1].get_text(strip=True)
                        if not title or "no tenders" in title.lower():
                            continue
                            
                        buyer = "Transnet " + cols[2].get_text(strip=True)
                        closing = cols[3].get_text(strip=True)
                        category = self.categorize_tender(title, "")
                        
                        tender_id_raw = cols[0].get_text(strip=True)
                        tender = {
                            'source': 'Transnet',
                            'tender_id': f"TN-{datetime.now().year}-{tender_id_raw}",
                            'title': title,
                            'buyer': buyer,
                            'category': category,
                            'closing_date': closing,
                            'days_remaining': self.calculate_days_remaining(closing),
                            'value_zar': 0,
                            'description': title,
                            'document_link': f"{self.base_url}{cols[1].find('a')['href'] if cols[1].find('a') and cols[1].find('a').has_attr('href') else ''}",
                            'priority_buyer': any(pb.lower() in buyer.lower() for pb in PRIORITY_BUYERS)
                        }
                        
                        tenders.append(tender)
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            logger.error(f"Error scraping Transnet: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                        
        logger.info(f"Scraped {len(tenders)} tenders from Transnet")
        return tenders

# ============== MAIN ORCHESTRATOR ==============

class TenderTracker:
    def __init__(self):
        self.sheets = GoogleSheetsManager(GOOGLE_SHEET_URL, SERVICE_ACCOUNT_FILE)
        self.alerter = EmailAlerter(SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, 
                                   EMAIL_PASSWORD, ALERT_RECIPIENTS)
        self.scrapers = {
            'etenders': ETendersScraper(
                username=os.getenv('ETENDERS_USERNAME'),
                password=os.getenv('ETENDERS_PASSWORD')
            ),
            'easytenders': EasyTendersScraper(),
            'transnet': TransnetScraper()
        }
        
    def run(self):
        """Execute full scraping and alerting workflow"""
        logger.info("=" * 60)
        logger.info("STARTING TENDER TRACKER SCRAPER")
        logger.info("=" * 60)
        
        # Get existing tender IDs to avoid duplicates
        existing_ids = self.sheets.get_existing_tender_ids()
        logger.info(f"Found {len(existing_ids)} existing tenders in database")
        
        all_new_tenders = []
        
        # Run all scrapers
        for name, scraper in self.scrapers.items():
            try:
                logger.info(f"Running scraper: {name}")
                tenders = scraper.scrape()
                
                for tender in tenders:
                    if tender['tender_id'] not in existing_ids:
                        all_new_tenders.append(tender)
                        
            except Exception as e:
                logger.error(f"Scraper {name} failed: {e}")
                continue
        
        logger.info(f"Found {len(all_new_tenders)} new tenders")
        
        # Process new tenders
        stats = {'insurance': {'count': 0, 'total_value': 0}}
        
        # Filter and Process new tenders - INSURANCE ONLY
        # Keep ONLY insurance category tenders
        filtered_tenders = []
        for tender in all_new_tenders:
            is_insurance = tender.get('category') == 'insurance'
            
            # STRICT FILTERING: Only keep insurance tenders
            if not is_insurance:
                logger.debug(f"Discarded non-insurance tender: {tender.get('title', 'unknown')[:50]}")
                continue
                
            filtered_tenders.append(tender)

        if filtered_tenders:
            if self.sheets.add_tenders(filtered_tenders):
                for tender in filtered_tenders:
                    # Update stats
                    cat = tender['category']
                    stats[cat]['count'] += 1
                    stats[cat]['total_value'] += tender.get('value_zar', 0)
                    
                    # All filtered tenders are insurance - send alert for all
                    # No need to check priority_buyer since we only keep insurance
                    self.alerter.send_alert(tender)
                    time.sleep(1)  # Minimal delay for alerts
        
        logger.info(f"Processed {len(filtered_tenders)} and discarded {len(all_new_tenders) - len(filtered_tenders)} noisy tenders.")
        
        # Update dashboard
        self.sheets.update_dashboard(stats)
        
        logger.info("=" * 60)
        logger.info("SCRAPER COMPLETED SUCCESSFULLY")
        logger.info(f"New tenders added: {len(filtered_tenders)}")
        logger.info("=" * 60)

# ============== ENTRY POINT ==============

if __name__ == "__main__":
    tracker = TenderTracker()
    tracker.run()
