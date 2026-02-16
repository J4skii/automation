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

# Categories and Keywords
CATEGORIES = {
    "insurance": {
        "keywords": ["insurance", "broker", "risk management", "underwriting", 
                    "policy", "premium", "claim", "sasria", "fidelity", 
                    "liability", "indemnity", "surety", "bond", "actuarial", 
                    "loss control", "marine", "aviation", "motor fleet",
                    "short-term", "medical aid", "pension", "provident", "guarantee"],
        "priority": 1
    },
    "advisory_consulting": {
        "keywords": ["advisory", "consultant", "consulting", "risk advisory",
                    "financial advisory", "strategy", "actuarial services",
                    "management consulting", "business advisory", "feasibility",
                    "audit", "internal audit", "forensic", "governance", "professional services"],
        "priority": 2
    },
    "civil_engineering": {
        "keywords": ["civil engineering", "infrastructure", "roads", "bridges",
                    "water", "sewer", "stormwater", "earthworks", "structural",
                    "pavement", "drainage", "bulk services"],
        "priority": 3
    },
    "cleaning_facility": {
        "keywords": ["cleaning", "facilities", "facility management", "hygiene",
                    "sanitation", "waste management", "grounds maintenance",
                    "janitorial", "pest control", "landscaping"],
        "priority": 4
    },
    "construction": {
        "keywords": ["construction", "building", "renovation", "refurbishment",
                    "structural", "concrete", "roofing", "painting", "electrical",
                    "plumbing", "HVAC", "maintenance", "alterations"],
        "priority": 5
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
    
    def add_tenders(self, tenders_data):
        """Add multiple tenders to Raw_Data sheet in one batch"""
        if not tenders_data:
            return True
            
        try:
            ws = self.sheet.worksheet('Raw_Data')
            
            rows = []
            for tender_data in tenders_data:
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
            # Try multiple date formats
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %B %Y']
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

class ETendersScraper(BaseScraper):
    """Scraper for eTenders.gov.za"""
    
    def __init__(self, username=None, password=None):
        super().__init__()
        self.base_url = "https://www.etenders.gov.za"
        self.username = username
        self.password = password
        
    def login(self):
        """Login to eTenders (if credentials provided)"""
        if not self.username or not self.password:
            logger.info("No credentials provided, scraping public tenders only")
            return True
            
        try:
            self._init_selenium()
            self.driver.get(f"{self.base_url}/Home/Login")
            
            # Wait for login form
            wait = WebDriverWait(self.driver, 10)
            username_field = wait.until(EC.presence_of_element_located((By.ID, "Username")))
            password_field = self.driver.find_element(By.ID, "Password")
            
            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            
            # Click login
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Wait for dashboard
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dashboard")))
            logger.info("Logged in to eTenders successfully")
            return True
            
        except Exception as e:
            logger.error(f"eTenders login failed: {e}")
            return False
    
    def scrape(self):
        """Scrape tender opportunities"""
        tenders = []
        
        try:
            if not self.driver:
                self._init_selenium()
                
            self.driver.get(f"{self.base_url}/Home/opportunities?id=1")
            
            # Wait for the table to load
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_element_located((By.ID, "tendeList")))
            
            # Give it a second for rows to render
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find tender table/rows
            # The structure often has rows inside the table id 'tendeList'
            table = soup.find('table', id='tendeList')
            if not table:
                logger.warning("eTenders table 'tendeList' not found in page source")
                return []

            tender_rows = table.find_all('tr')[1:] # Skip header
            
            for row in tender_rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) < 5:
                        continue
                    
                    title = cols[2].get_text(strip=True)
                    # Skip if it's a dummy row or just says "Loading..."
                    if "loading" in title.lower() or not title:
                        continue
                        
                    buyer = cols[1].get_text(strip=True)
                    closing_date = cols[5].get_text(strip=True)
                    category = self.categorize_tender(title, "")
                    
                    tender = {
                        'source': 'eTenders.gov.za',
                        'tender_id': f"ET-{datetime.now().year}-{hash(title) % 10000:04d}",
                        'title': title,
                        'buyer': buyer,
                        'category': category,
                        'closing_date': closing_date,
                        'days_remaining': self.calculate_days_remaining(closing_date),
                        'value_zar': 0,
                        'description': title,
                        'document_link': f"{self.base_url}{cols[2].find('a')['href'] if cols[2].find('a') else ''}",
                        'priority_buyer': any(pb.lower() in buyer.lower() for pb in PRIORITY_BUYERS)
                    }
                    
                    tenders.append(tender)
                    
                except Exception as e:
                    logger.warning(f"Error parsing eTenders row: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping eTenders: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                
        logger.info(f"Scraped {len(tenders)} tenders from eTenders")
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
                for keyword in data['keywords'][:5]:  # Top 5 keywords per category
                    try:
                        search_url = f"{self.base_url}/tenders?search={keyword}"
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
        stats = {cat: {'count': 0, 'total_value': 0} for cat in CATEGORIES.keys()}
        stats['uncategorized'] = {'count': 0, 'total_value': 0}
        
        # Filter and Process new tenders
        filtered_tenders = []
        for tender in all_new_tenders:
            is_priority = tender.get('priority_buyer', False)
            is_categorized = tender.get('category') != 'uncategorized'
            
            # STRICT FILTERING: Discard if uncategorized AND NOT a priority buyer
            if not is_categorized and not is_priority:
                continue
                
            filtered_tenders.append(tender)

        if filtered_tenders:
            if self.sheets.add_tenders(filtered_tenders):
                for tender in filtered_tenders:
                    # Update stats
                    cat = tender['category']
                    stats[cat]['count'] += 1
                    stats[cat]['total_value'] += tender.get('value_zar', 0)
                    
                    # Send alert for priority buyers or insurance-related
                    if tender['priority_buyer'] or tender['category'] == 'insurance':
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
