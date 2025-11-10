from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import os
import json
from pathlib import Path
from typing import List


def get_google_credentials(scopes: List[str]) -> service_account.Credentials:
    """
    Authenticates with Google APIs using service account credentials.

    It first looks for a 'credentials.json' file in the project root.
    If not found, it falls back to the 'GOOGLE_CREDENTIALS' environment variable.

    Args:
        scopes (List[str]): A list of scopes to request during authentication.

    Returns:
        service_account.Credentials: The authenticated credentials object.

    Raises:
        ValueError: If credentials are not found in either the file or environment variable.
    """
    project_root = Path(__file__).resolve().parent.parent
    cred_path = project_root / ".secrets" / "google_drive_credentials.json"

    if cred_path.exists():
        return service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)

    if cred_info_str := os.environ.get("GOOGLE_CREDENTIALS"):
        cred_info = json.loads(cred_info_str)
        return service_account.Credentials.from_service_account_info(cred_info, scopes=scopes)

    raise ValueError("Google credentials not found. Please set GOOGLE_CREDENTIALS or provide a credentials.json file.")


def get_telegram_token() -> str:
    """
    Retrieves the Telegram bot token.

    It first looks for the 'TELEGRAM_BOT_TOKEN' environment variable.
    If not found, it falls back to a 'telegram_bot_token' key in the
    '.secrets/other_secrets.json' file.

    Returns:
        str: The Telegram bot token.

    Raises:
        ValueError: If the token is not found in either the environment variable or the file.
    """
    if token := os.environ.get("TELEGRAM_BOT_TOKEN"):
        return token

    project_root = Path(__file__).resolve().parent.parent
    secrets_path = project_root / ".secrets" / "other_credentials.json"

    if secrets_path.exists():
        with open(secrets_path) as f:
            secrets = json.load(f)
            if token := secrets.get("telegram_bot_token"):
                return token

    raise ValueError("Telegram token not found. Please set TELEGRAM_BOT_TOKEN or provide it in .secrets/other_secrets.json.")