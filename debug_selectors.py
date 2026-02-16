import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URLS = {
    "etenders": "https://www.etenders.gov.za/Home/opportunities?id=1",
    "easytenders": "https://easytenders.co.za/tenders?search=insurance",
    "transnet": "https://transnetetenders.azurewebsites.net/Home/AdvertisedTenders"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def debug_scrape():
    for name, url in URLS.items():
        logger.info(f"--- Checking {name}: {url} ---")
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            logger.info(f"Status Code: {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if name == "etenders":
                rows = soup.find_all('tr')
                print(f"ETENDERS: Found {len(rows)} tr tags")
                for i, row in enumerate(rows[:5]):
                    print(f"  Row {i}: class={row.get('class')}")
                
                # Check for table
                tables = soup.find_all('table')
                print(f"ETENDERS: Found {len(tables)} tables")
                for i, table in enumerate(tables):
                    print(f"  Table {i} id={table.get('id')} class={table.get('class')}")

            elif name == "easytenders":
                cards = soup.find_all('div', class_='tender-card')
                print(f"EASYTENDERS: Found {len(cards)} 'tender-card' divs")
                
                # If no cards, check for any 'card' like structures
                if not cards:
                    all_divs = soup.find_all('div')
                    print(f"EASYTENDERS: total divs={len(all_divs)}")
                    div_classes = set()
                    for d in all_divs:
                        if d.get('class'):
                            div_classes.update(d.get('class'))
                    print(f"EASYTENDERS: unique div classes (first 30): {list(div_classes)[:30]}")

            elif name == "transnet":
                table = soup.find('table', {'id': 'tenderTable'})
                if table:
                    print("TRANSNET: Found table 'tenderTable'")
                    rows = table.find_all('tr')
                    print(f"TRANSNET: table has {len(rows)} rows total")
                else:
                    print("TRANSNET: table 'tenderTable' NOT found")
                    tables = soup.find_all('table')
                    print(f"TRANSNET: Found {len(tables)} tables")
                    for t in tables:
                        print(f"  Table id={t.get('id')} class={t.get('class')}")

            # Print a snippet of the body if nothing found
            if response.status_code == 200 and len(response.text) < 500:
                logger.info(f"Page content too short: {response.text}")

        except Exception as e:
            logger.error(f"Error checking {name}: {e}")

if __name__ == "__main__":
    debug_scrape()
