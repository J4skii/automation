Praeto Tender Tracker
  Automated tender scraping system for South African government tender portals.

What It Does
  Scrapes tenders from eTenders.gov.za, EasyTenders.co.za, and Transnet eTenders
  Categorizes by industry (Insurance, Advisory, Engineering, etc.)
  Sends daily email alerts for priority buyers
  Stores all data in Google Sheets for easy tracking
🛠 Tech Stack
Python 3.8+ | Selenium | BeautifulSoup | gspread | Streamlit
Features
  Multi-source scraping (REST API + Selenium)
  Smart date parsing (handles multiple formats)
  Automatic deduplication
  Priority buyer flagging
  Email notifications
  Interactive dashboard
 Key Files
  tender_scraper.py - Main scraper
  dashboard.py - Streamlit dashboard
  TECHNICAL_DOCUMENTATION.md - Full setup guide
Notes
  Requires service_account.json from Google Cloud Console
  Environment variable: EMAIL_PASSWORD
Star ⭐ the repo if you find it useful!
