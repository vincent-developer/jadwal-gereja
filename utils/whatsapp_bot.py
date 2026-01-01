import os
import re
import requests
from dotenv import load_dotenv, find_dotenv

# Load .env
load_dotenv(find_dotenv())

BAILEYS_ERROR_MAP = {
    400: "Bad Request (payload invalid)",
    401: "Unauthorized (token invalid)",
    403: "Forbidden",
    404: "Endpoint not found",
    409: "WhatsApp session not ready / conflict",
    429: "Rate limit exceeded",
    500: "Internal server error (Baileys crash)",
}

class WhatsAppSendError(Exception):
    """Base exception for WhatsApp send failures."""
    pass


class WhatsAppValidationError(WhatsAppSendError):
    pass


class WhatsAppAPIError(WhatsAppSendError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class WhatsAppNetworkError(WhatsAppSendError):
    pass




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

    def send(self, number: str, message: str) -> dict:
        """Send a WhatsApp message via Baileys API.

        :raises WhatsAppValidationError
        :raises WhatsAppNetworkError
        :raises WhatsAppAPIError
        :return: response JSON
        """

        # 1️⃣ Normalize & validate number
        try:
            formatted = self.normalize_number(number)
        except ValueError as e:
            raise WhatsAppValidationError(str(e))

        payload = {
            "number": formatted,
            "message": message
        }

        # 2️⃣ HTTP request
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
        except requests.exceptions.RequestException as e:
            raise WhatsAppNetworkError(f"Network error: {e}")

        # 3️⃣ Handle non-200 response
        if response.status_code != 200:
            error_message = BAILEYS_ERROR_MAP.get(
                response.status_code,
                response.text
            )

            raise WhatsAppAPIError(
                status_code=response.status_code,
                message=error_message
            )

        # 4️⃣ Success
        return response.json()
