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

        if not self.base_url:
            raise ValueError("WHATSAPP_URL not found in environment.")

    def normalize_number(self, number: str) -> str:
        """
        valid for indonesian number only
        Validate and normalize phone number to format:
        628xxxxxxxxx
        """

        # Remove spaces, dash, parentheses, and keep digits + optional plus
        cleaned = re.sub(r"[^0-9+]", "", number)

        # If it contains letters -> error
        if re.search(r"[A-Za-z]", cleaned):
            raise ValueError("Phone number must not contain letters.")

        # Remove leading +
        cleaned = cleaned.lstrip("+")

        # RULES:
        # If starts with "0" -> replace with "62"
        if cleaned.startswith("0"):
            cleaned = "62" + cleaned[1:]

        # If missing "62" but starts with 8 (ex: 812xxx)
        elif cleaned.startswith("8"):
            cleaned = "62" + cleaned

        # If already starting with 62 → leave as is
        elif cleaned.startswith("62"):
            pass  # Valid

        else:
            raise ValueError(f"Invalid phone format: {number}")

        # Final validation: must contain only numbers
        if not cleaned.isdigit():
            raise ValueError(f"Phone number contains invalid characters: {number}")

        # Optional: minimum length check (WhatsApp typical: >= 10)
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

        payload = {"number": formatted, "message": message}

        try:
            response = requests.post(self.base_url, json=payload, timeout=10)

            if response.status_code == 200:
                print(f"✅ Sent WhatsApp to {formatted}: {message}")
                return response.json()
            else:
                print(f"⚠️ API responded with {response.status_code}: {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Network Error: {e}")
            return None
