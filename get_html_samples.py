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

def get_samples():
    print("=== SAMPLES ===")
    for name, url in URLS.items():
        try:
            res = requests.get(url, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(res.content, 'html.parser')
            
            print(f"\n--- {name} Sample ---")
            if name == "etenders":
                table = soup.find('table', id='tendeList')
                if table:
                    print(str(table)[:1000])
                else:
                    print("tendeList NO")
            
            elif name == "easytenders":
                card = soup.find('div', class_='tender')
                if card:
                    print(str(card)[:1000])
                else:
                    all_cards = soup.find_all('div', class_='card')
                    if all_cards:
                        print(f"Found {len(all_cards)} cards. First card:")
                        print(str(all_cards[0])[:1000])
            
            elif name == "transnet":
                table = soup.find('table', id='_advertisedTenders')
                if table:
                    print(str(table)[:1000])
                else:
                    print("_advertisedTenders NO")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    get_samples()
