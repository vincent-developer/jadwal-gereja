import os
import re
import requests
from dotenv import load_dotenv, find_dotenv

# Load .env
load_dotenv(find_dotenv())


class WhatsAppBot:
    """WhatsApp REST API Client with number validation."""

    def __init__(self):
        self.base_url = os.getenv("WHATSAPP_URL")
        self.token = os.getenv("WHATSAPP_BOT_TOKEN")

        if not self.base_url:
            raise ValueError("WHATSAPP_URL not found in environment.")

        if not self.token:
            raise ValueError("WHATSAPP_BOT_TOKEN not found in environment.")

        # Prepare headers once
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def normalize_number(self, number: str) -> str:
        """
        valid for indonesian number only
        Normalize phone number to format: 628xxxxxxxxx
        """

        cleaned = re.sub(r"[^0-9+]", "", number)

        if re.search(r"[A-Za-z]", cleaned):
            raise ValueError("Phone number must not contain letters.")

        cleaned = cleaned.lstrip("+")

        if cleaned.startswith("0"):
            cleaned = "62" + cleaned[1:]
        elif cleaned.startswith("8"):
            cleaned = "62" + cleaned
        elif cleaned.startswith("62"):
            pass
        else:
            raise ValueError(f"Invalid phone format: {number}")

        if not cleaned.isdigit():
            raise ValueError(f"Phone number contains invalid characters: {number}")

        if len(cleaned) < 10:
            raise ValueError(f"Phone number too short: {number}")

        return cleaned

    def send(self, number: str, message: str):
        """Send a WhatsApp message."""

        try:
            formatted = self.normalize_number(number)
        except ValueError as e:
            print(f"❌ Number Validation Failed: {e}")
            return None

        payload = {
            "number": formatted,
            "message": message
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✅ Sent WhatsApp to {formatted}")
                return response.json()

            print(f"⚠️ API Error {response.status_code}: {response.text}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Network Error: {e}")
            return None
