"""
Choir data model
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Choir:
    """Represents a Choir group with coordinator and contact information"""
    
    choir_name: str
    wa_number: Optional[str] = None
    coordinator_name: Optional[str] = None
    
    def has_whatsapp(self) -> bool:
        """Check if choir has WhatsApp contact"""
        # Cek standar: tidak None dan tidak kosong
        return self.wa_number is not None and self.wa_number.strip() != ""
    
    def __str__(self) -> str:
        return f"Choir({self.choir_name})"