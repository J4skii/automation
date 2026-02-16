import gspread
from google.oauth2.service_account import Credentials
import logging
import sys

# Configure logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

SERVICE_ACCOUNT_FILE = "service_account.json"
GOOGLE_SHEET_ID = "1pHXkYhOyXrKsHP7syDK_WfQh3xy-Qn-hHdJLNlV0mbg"

def test_connection():
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        logger.info(f"Loading credentials from {SERVICE_ACCOUNT_FILE}...")
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scope
        )
        client = gspread.authorize(creds)
        
        logger.info("Listing all spreadsheets shared with this service account...")
        shared_sheets = client.openall()
        if not shared_sheets:
            logger.warning("No spreadsheets found! This usually means the Sheet hasn't been shared with the service account email correctly.")
        else:
            for gsheet in shared_sheets:
                logger.info(f"Found Share: {gsheet.title} (ID: {gsheet.id})")

        logger.info(f"Attempting to open specific sheet by ID: {GOOGLE_SHEET_ID}")
        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        logger.info(f"SUCCESS: Connected to '{sheet.title}'")
        
        worksheets = [ws.title for ws in sheet.worksheets()]
        logger.info(f"Worksheets found: {worksheets}")
        
    except FileNotFoundError:
        logger.error(f"Error: {SERVICE_ACCOUNT_FILE} not found in the current directory.")
    except gspread.exceptions.APIError as e:
        logger.error(f"API Error: {e}")
        if 'PERMISSIONS_DENIED' in str(e) or '403' in str(e):
            logger.error("ACCESS DENIED: Please ensure the Google Sheets and Google Drive APIs are ENABLED in the Google Cloud Console.")
    except Exception as e:
        logger.error(f"Unexpected Error {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_connection()
