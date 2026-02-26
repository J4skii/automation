# Praeto Tender Tracker - Technical Documentation

## Overview

**Project Name:** Praeto Tender Tracker  
**Version:** 1.0  
**Last Updated:** 2026-02-26  
**Author:** Automation System

### Description

Automated scraper for South African tender portals that collects, categorizes, and alerts on government tenders. Outputs to Google Sheets and sends email notifications.

### Target Tender Sources

| Source | URL | Scraping Method |
|--------|-----|-----------------|
| eTenders.gov.za | https://www.etenders.gov.za | JSON API (DataTables) |
| EasyTenders.co.za | https://www.easytenders.co.za | HTTP Requests + BeautifulSoup |
| Transnet eTenders | https://transnetetenders.azurewebsites.net | Selenium (headless Chrome) |

---

## Tech Stack

### Programming Language
- **Python 3.8+**

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| requests | 2.31.0 | HTTP requests |
| beautifulsoup4 | 4.12.2 | HTML parsing |
| selenium | 4.15.2 | Browser automation |
| gspread | 5.12.0 | Google Sheets API |
| google-auth | 2.23.0 | Authentication |
| pandas | latest | Data processing |
| streamlit | latest | Dashboard UI |
| plotly | latest | Charts |

### Installation

```bash
# Clone the repository
git clone https://github.com/J4skii/automation.git
cd automation

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

---

## Google Cloud Setup

### Step 1: Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g., "PraetoTenderTracker")
3. Enable APIs:
   - Google Sheets API
   - Google Drive API

### Step 2: Create Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Create service account (e.g., "tender-scraper")
3. Download JSON key file
4. Rename to `service_account.json` and place in project root
5. **Important:** Share your Google Sheet with the service account email (shown in the JSON file) as **Editor**

### Step 3: Configure Sheet

Your Google Sheet URL is hardcoded in [`tender_scraper.py`](tender_scraper.py:41):
```
https://docs.google.com/spreadsheets/d/1pHXkYhOyXrKsHP7syDK_WfQh3xy-Qn-hHdJLNlV0mbg/edit
```

Required worksheets:
- **Raw_Data** - Contains scraped tenders
- **Dashboard** - Summary statistics
- **Settings** - Configuration
- **Priority_Buyers** - Priority buyer list
- **Categories** - Category definitions

---

## Configuration

### Google Sheets Configuration

```python
# tender_scraper.py - Line 40-42
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
SERVICE_ACCOUNT_FILE = "service_account.json"
```

### Email Configuration

```python
# tender_scraper.py - Line 44-55
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
```

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Windows
set EMAIL_PASSWORD=your_password

# Linux/Mac
export EMAIL_PASSWORD=your_password
```

### Categories and Keywords

```python
# tender_scraper.py - Line 57-72
CATEGORIES = {
    "insurance": {
        "keywords": ["insurance", "broker", "risk management", ...],
        "priority": 1
    }
}
```

### Priority Buyers

```python
# tender_scraper.py - Line 75+
PRIORITY_BUYERS = [
    "Chief Albert Luthuli Municipality",
    "Financial and Fiscal Commission",
    "CIDB",
    ...
]
```

---

## Running the Scraper

### Basic Run

```bash
python tender_scraper.py
```

### Scheduled Runs

The script can be scheduled using Windows Task Scheduler or cron:

```bash
# Run every day at 6 AM
python -c "
import schedule
import time
from tender_scraper import run_full_scrape

schedule.every().day.at('06:00').do(run_full_scrape)

while True:
    schedule.run_pending()
    time.sleep(60)
"
```

---

## Output Format

### Google Sheets Column Mapping

| Column | Field | Description |
|--------|-------|-------------|
| A | Date_Scraped | Date when tender was scraped (YYYY-MM-DD) |
| B | Source | Tender source (eTenders, EasyTenders, Transnet) |
| C | Tender_ID | Unique tender ID |
| D | Title | Tender title |
| E | Buyer | Procuring organization |
| F | Category | Category (insurance, etc.) |
| G | Closing_Date | Tender closing date |
| H | Days_Remaining | Days until closing |
| I | Description | Tender description (truncated) |
| J | Document_Link | Link to tender documents |

---

## Code Structure

### Main Classes

| Class | File | Purpose |
|-------|------|---------|
| BaseScraper | tender_scraper.py | Base class with common methods |
| ETendersScraper | tender_scraper.py | Scrapes etenders.gov.za |
| EasyTendersScraper | tender_scraper.py | Scrapes easytenders.co.za |
| TransnetScraper | tender_scraper.py | Scrapes transnetetenders |
| GoogleSheetsManager | tender_scraper.py | Handles Google Sheets operations |
| EmailAlerter | tender_scraper.py | Sends email notifications |

### Key Methods

```python
# Date handling
BaseScraper.calculate_days_remaining(closing_date_str, source)
BaseScraper.parse_easytenders_date(raw_date_text)

# Categorization
BaseScraper.categorize_tender(title, description)

# Google Sheets
GoogleSheetsManager.add_tenders(tenders_data)
GoogleSheetsManager.validate_tender_data(tender_data)
GoogleSheetsManager.auto_fix_tender(tender)

# Main entry
run_full_scrape()  # Runs all scrapers and sends to Sheets
```

---

## Troubleshooting

### Common Issues

#### 1. Google Sheets Not Populating

**Symptoms:** Script runs but no data appears in Google Sheets

**Solutions:**
1. Check `service_account.json` exists in project root
2. Verify sheet is shared with service account email (with Editor access)
3. Check Google Cloud Console - ensure Sheets API is enabled
4. Run with verbose logging to see errors

#### 2. Date Parsing Issues

**Symptoms:** Days_Remaining shows 0 or wrong values

**Solutions:**
- The system now handles multiple date formats:
  - ISO: `2026-03-27`
  - EasyTenders: `Closing 18 Mar`
  - Various: `27/03/2026`, `27 March 2026`

#### 3. Selenium/Transnet Issues

**Symptoms:** Transnet scraper fails

**Solutions:**
1. Ensure Chrome browser is installed
2. Check ChromeDriver compatibility
3. Try running: `python diagnose_selenium.py`

#### 4. Email Not Sending

**Symptoms:** No email alerts received

**Solutions:**
1. Verify EMAIL_PASSWORD environment variable is set
2. Check SMTP settings for your email provider
3. Ensure less secure app access is enabled (if using Gmail)

### Debugging Tools

```bash
# Test Google Sheets connection
python test_sheet_connection.py

# Test date parsing
python -c "
from tender_scraper import BaseScraper
s = BaseScraper()
print(s.calculate_days_remaining('2026-03-27', 'eTenders'))
print(s.calculate_days_remaining('Closing 18 Mar', 'EasyTenders'))
"

# Get HTML samples for debugging
python get_html_samples.py

# Debug selectors
python debug_selectors.py
```

---

## Maintenance

### Updating Keywords

Edit the `CATEGORIES` dictionary in [`tender_scraper.py`](tender_scraper.py:57-72):

```python
CATEGORIES = {
    "insurance": {
        "keywords": ["new keyword1", "new keyword2", ...],
        "priority": 1
    }
}
```

### Adding New Sources

1. Create new class inheriting from `BaseScraper`
2. Implement `scrape()` method
3. Add to `SCRAPERS` list
4. Update `run_full_scrape()` function

### Changing Sheet Structure

If you modify columns in the code, you must:
1. Update `add_tenders()` method in `GoogleSheetsManager`
2. Manually update your Google Sheet headers

---

## File Inventory

| File | Purpose |
|------|---------|
| tender_scraper.py | Main scraper (40KB+) |
| dashboard.py | Streamlit dashboard |
| requirements.txt | Python dependencies |
| service_account.json | Google credentials (NOT in repo) |
| .env | Environment variables (NOT in repo) |
| diagnose_selenium.py | Selenium debugging |
| debug_selectors.py | Selector debugging |
| get_html_samples.py | HTML sample collection |
| test_sheet_connection.py | Sheets connection test |
| test_post_method.py | POST method testing |
| analyze_sites.py | Site analysis |

---

## Security Notes

- **NEVER** commit `service_account.json` to Git
- **NEVER** commit `.env` to Git
- Both are in `.gitignore` for a reason
- Use environment variables for sensitive data

---

## Support

For issues or questions:
1. Check this documentation
2. Run diagnostic scripts
3. Check logs in console output
4. Examine Google Sheet for error messages

---

## Changelog

### 2026-02-26
- Removed Value_ZAR, Status, Priority_Buyer, Alert_Sent columns
- Enhanced date parsing with source-specific logic
- Added validation and auto-fix in GoogleSheetsManager
- Updated calculate_days_remaining to handle multiple formats

### 2026-02-25
- Initial fixes for EasyTenders date parsing
- Added validation layer for Google Sheets
- Source parameter added to date calculations
