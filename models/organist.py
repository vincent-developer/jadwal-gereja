"""
Organist data model
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Organist:
    """Represents an organist with contact information"""
    
    name: str
    telegram_chat_id: Optional[str] = None
    wa_number: Optional[str] = None
    
    def has_telegram(self) -> bool:
        """Check if organist has Telegram contact"""
        return self.telegram_chat_id is not None and self.telegram_chat_id.strip() != ""
    
    def has_whatsapp(self) -> bool:
        """Check if organist has WhatsApp contact"""
        return self.wa_number is not None and self.wa_number.strip() != ""
    
    def __str__(self) -> str:
        return f"Organist({self.name})"