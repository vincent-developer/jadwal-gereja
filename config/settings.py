import os
import json
from pathlib import Path
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = PROJECT_ROOT / ".secrets"

# Google Sheets scopes
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]


def get_google_credentials() -> service_account.Credentials:
    """
    Get Google service account credentials.
    Priority: credentials.json file → GOOGLE_CREDENTIALS env var
    
    Returns:
        service_account.Credentials: Authenticated credentials
        
    Raises:
        ValueError: If credentials not found
    """
    cred_path = SECRETS_DIR / "google_drive_credentials.json"
    
    if cred_path.exists():
        return service_account.Credentials.from_service_account_file(
            cred_path, 
            scopes=GOOGLE_SCOPES
        )
    
    if cred_info_str := os.getenv("GOOGLE_CREDENTIALS"):
        cred_info = json.loads(cred_info_str)
        return service_account.Credentials.from_service_account_info(
            cred_info, 
            scopes=GOOGLE_SCOPES
        )
    
    raise ValueError(
        "Google credentials not found. "
        "Please provide credentials.json in .secrets/ or set GOOGLE_CREDENTIALS env var."
    )
    
# Google Sheets - Master Data (source/input)
MASTER_SPREADSHEET_ID = "1xMNjbpQJhh8jTOaNlxPWy9B2nTEMBAURR9Ys3O90jlM"
MASTER_SCHEDULE_SHEET_NAME = "Jadwal Pasdior"

# Google Sheets - Database (output/storage)
DATABASE_SPREADSHEET_ID = "1nqY5jNzJvsy7v37jnb-rlSDUNvsLYiuHq5-ryAW1Kxs"
DATABASE_ORGANIST_SHEET_NAME = "Data Organis"
DATABASE_LOG_SHEET_NAME = "Notification Chat Log"  # ini kan juga di database

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")

# WhatsApp  
WHATSAPP_BOT_TOKEN = os.getenv("WHATSAPP_BOT_TOKEN")
WHATSAPP_URL = os.getenv("WHATSAPP_URL")