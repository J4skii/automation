"""
Test script to check if eTenders POST form submission works
"""
import requests
from bs4 import BeautifulSoup

def test_post_method():
    url = "https://www.etenders.gov.za/Home/Opportunities"
    
    # Test with one insurance category
    data = {
        'Category': 'Financial and insurance activities',
        'Province': '',
        'OrganOfState': '',
        'TenderType': '',
        'searchString': '',
        'applyFilters': 'Apply filters'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://www.etenders.gov.za/Home/opportunities'
    }
    
    print("Testing POST request to eTenders...")
    print(f"URL: {url}")
    print(f"Data: {data}")
    print()
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)}")
        print(f"Has <table>: {'<table' in response.text}")
        print(f"Has tenderList: {'tenderList' in response.text}")
        print(f"Has tendeList: {'tendeList' in response.text}")
        print()
        
        # Check if we got results
        if '<table' in response.text:
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', id='tenderList') or soup.find('table', id='tendeList')
            if table:
                rows = table.find_all('tr')
                print(f"✅ SUCCESS! Found table with {len(rows)} rows")
                
                # Show first few rows
                print("\nFirst few tenders:")
                for i, row in enumerate(rows[1:6], 1):
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        print(f"  {i}. {cols[2].get_text(strip=True)[:60]}")
                return True
            else:
                print("⚠️ Table found but no ID match")
        else:
            print("❌ No table found in response")
            # Check what we got
            print("\nFirst 500 chars of response:")
            print(response.text[:500])
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_post_method()
