"""
Constants that don't change across environments
"""

# =======================================
# TIMEZONE & LOCALE
# =======================================
JAKARTA_TZ = "Asia/Jakarta"
INDONESIAN_LOCALE = "id"

# =======================================
# MONTH MAPPING
# =======================================
MONTH_MAP = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Sept": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}

# =======================================
# LITURGICAL YEAR
# =======================================
LITURGICAL_YEAR_MAP = {
    1: "A",
    2: "B", 
    0: "C"
}

# =======================================
# WEEKDAYS (Indonesian)
# =======================================
WEEKEND_DAYS = ["Sabtu", "Minggu", "Saturday", "Sunday"]

# =======================================
# MESSAGE TEMPLATES
# =======================================
# Shared footer for highlight-card reminder messages (organist & choir).
REMINDER_HIGHLIGHT_FOOTER = (
    "---\n"
    "Cek jadwal lebih update di: https://linktr.ee/pasdiormabes\n\n"
    "Catatan:\n"
    "- Jangan balas pesan ini. Kendala jadwal bisa didiskusikan di grup WhatsApp.\n"
    "- Sistem ini di-maintain secara volunteer oleh Vincent (vincent.koci.kusuma@gmail.com)"
)

# Daftar Jenis Lagu (Ordinarium)
ORDINARIUM_TYPES = [
    "laudasion", 
    "misa kita 2", 
    "misa kita 4", 
    "misa manado", 
    "misa raya 2"
]

# Daftar Versi Bapa Kami
BAPA_KAMI_VERSIONS = [
    "ps 404", 
    "ps 405", 
    "konvennas", 
    "putut", 
    "totok", 
    "cbd"
]