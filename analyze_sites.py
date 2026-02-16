import requests
from bs4 import BeautifulSoup

URLS = {
    "etenders": "https://www.etenders.gov.za/Home/opportunities?id=1",
    "easytenders": "https://easytenders.co.za/tenders?search=insurance",
    "transnet": "https://transnetetenders.azurewebsites.net/Home/AdvertisedTenders"
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def analyze_site(name, url):
    print(f"\n=== Analyzing {name} ===")
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
        print(f"Status: {res.status_code}, Length: {len(res.text)}")
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Look for tables
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables")
        for i, t in enumerate(tables):
            print(f"  Table {i}: id='{t.get('id')}', class='{t.get('class')}'")
            rows = t.find_all('tr')
            print(f"    - Rows: {len(rows)}")
            if rows:
                cols = rows[0].find_all(['td', 'th'])
                print(f"    - Cols in first row: {len(cols)}")
        
        # Look for card-like divs
        divs = soup.find_all('div')
        card_keywords = ['card', 'tender', 'item', 'row', 'listing']
        interesting_divs = []
        for d in divs:
            cls = d.get('class')
            if cls:
                if any(kw in str(cls).lower() for kw in card_keywords):
                    interesting_divs.append(str(cls))
        
        if interesting_divs:
            from collections import Counter
            counts = Counter(interesting_divs)
            print(f"Interesting div classes: {counts.most_common(10)}")

    except Exception as e:
        print(f"Error analyzing {name}: {e}")

if __name__ == "__main__":
    for name, url in URLS.items():
        analyze_site(name, url)
