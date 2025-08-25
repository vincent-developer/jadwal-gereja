from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# ---------- Google Drive / Sheets ----------
def get_google_credentials(scopes):
    
    # cari parent directory
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_path = os.path.join(parent_dir, "credentials.json")
    if os.path.exists(cred_path):
        return ServiceAccountCredentials.from_json_keyfile_name(cred_path, scopes)
    service_account_info = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    return ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scopes)