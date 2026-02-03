"""
Schedule data model
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Schedule:
    """Represents a mass schedule"""
    
    date: str  # Date string from sheet
    hour: str  # Time
    anamnesis: str
    cara_tobat: str
    koor: str
    organis: str
    formated_date: datetime  # Parsed datetime object
    liturgical_year: str  # A, B, or C
    day: str  # Day name in Indonesian
    weekday: str  # "yes" or "no"
    
    def is_weekday(self) -> bool:
        """Check if schedule is on a weekday"""
        return self.weekday.lower() == "yes"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame"""
        return {
            "Hari": self.day,
            "Tanggal": self.date,
            "Jam": self.hour,
            "Anamnesis": self.anamnesis,
            "Cara Tobat": self.cara_tobat,
            "Koor": self.koor,
            "Organis": self.organis,
            "Tahun Liturgi": self.liturgical_year,
            "Weekday": self.weekday,
        }
    
    def __str__(self) -> str:
        return f"Schedule({self.day}, {self.date} {self.hour} - {self.organis})"