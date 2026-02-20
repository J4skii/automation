"""Detailed site diagnosis using Selenium to capture JavaScript-rendered content"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    return webdriver.Chrome(options=options)

def diagnose_etenders():
    """Diagnose eTenders.gov.za with Selenium"""
    print("\n" + "="*60)
    print("DIAGNOSING ETENDERS.GOV.ZA")
    print("="*60)
    
    driver = setup_driver()
    try:
        driver.get("https://www.etenders.gov.za/Home/opportunities?id=1")
        
        # Wait for table to load
        print("Waiting for table to load...")
        time.sleep(5)  # Give extra time for JS to render
        
        # Try different wait strategies
        try:
            wait = WebDriverWait(driver, 15)
            table = wait.until(EC.presence_of_element_located((By.ID, "tendeList")))
            print(f"Found table with id='tendeList'")
        except Exception as e:
            print(f"Could not find tendeList table: {e}")
        
        # Get page source and parse
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find the table
        table = soup.find('table', id='tendeList')
        if table:
            rows = table.find_all('tr')
            print(f"Found {len(rows)} rows in table")
            
            # Print first few rows with cell contents
            for i, row in enumerate(rows[:5]):
                cells = row.find_all(['td', 'th'])
                print(f"\nRow {i} has {len(cells)} cells:")
                for j, cell in enumerate(cells):
                    text = cell.get_text(strip=True)[:50]
                    print(f"  Cell {j}: '{text}'")
        else:
            print("Table 'tendeList' not found!")
            
    finally:
        driver.quit()

def diagnose_easytenders():
    """Diagnose EasyTenders.co.za with Selenium"""
    print("\n" + "="*60)
    print("DIAGNOSING EASYTENDERS.CO.ZA")
    print("="*60)
    
    driver = setup_driver()
    try:
        driver.get("https://easytenders.co.za/tenders?search=insurance")
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find tender cards - try multiple selectors
        cards = soup.find_all('div', class_='tender')
        print(f"Found {len(cards)} divs with class='tender'")
        
        if cards:
            print("\nFirst tender card structure:")
            card = cards[0]
            
            # Print all child elements with text
            print("Card children:")
            for i, child in enumerate(card.find_all(recursive=False)[:10]):
                cls = child.get('class', [])
                text = child.get_text(strip=True)[:80]
                print(f"  {i}: <{child.name}> class={cls} -> '{text}'")
            
            # Try to find title, buyer, date
            print("\nTrying to extract common fields:")
            
            # Look for links (often contain tender title)
            links = card.find_all('a')
            print(f"  Found {len(links)} links")
            for i, link in enumerate(links[:3]):
                href = link.get('href', '')[:50]
                text = link.get_text(strip=True)[:50]
                print(f"    Link {i}: href={href}, text='{text}'")
            
            # Look for specific class patterns
            title_candidates = card.find_all(['h5', 'h6', 'div'], class_=lambda x: x and 'title' in str(x).lower())
            print(f"  Title candidates: {len(title_candidates)}")
            
        else:
            print("No tender cards found!")
            # Show some div classes
            all_divs = soup.find_all('div')
            classes = set()
            for d in all_divs:
                if d.get('class'):
                    classes.update(d.get('class'))
            print(f"Unique classes: {list(classes)[:20]}")
            
    finally:
        driver.quit()

def diagnose_transnet():
    """Diagnose Transnet with Selenium"""
    print("\n" + "="*60)
    print("DIAGNOSING TRANSNET ETENDERS")
    print("="*60)
    
    driver = setup_driver()
    try:
        driver.get("https://transnetetenders.azurewebsites.net/Home/AdvertisedTenders")
        time.sleep(5)  # Give time for AJAX to load
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Check for the table
        table = soup.find('table', id='_advertisedTenders')
        if table:
            rows = table.find_all('tr')
            print(f"Found {len(rows)} rows in _advertisedTenders")
            
            for i, row in enumerate(rows[:5]):
                cells = row.find_all(['td', 'th'])
                print(f"\nRow {i}: {len(cells)} cells")
                for j, cell in enumerate(cells):
                    text = cell.get_text(strip=True)[:50]
                    print(f"  Cell {j}: '{text}'")
        else:
            print("Table '_advertisedTenders' not found!")
            
        # Check if there's any table at all
        all_tables = soup.find_all('table')
        print(f"\nTotal tables on page: {len(all_tables)}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    diagnose_etenders()
    diagnose_easytenders()
    diagnose_transnet()
