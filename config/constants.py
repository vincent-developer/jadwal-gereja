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
REMINDER_MESSAGE_TEMPLATE = (
    "Hi {name}, jadwal organis berikutnya adalah:\n"
    "{schedule_list}\n\n"
    "Untuk jadwal yang lebih update silahkan cek di link berikut:\n"
    "https://linktr.ee/pasdiormabes\n\n"
    "Catatan:\n"
    "- Jangan balas pesan ini. Jika ada kendala jadwal, silahkan diskusikan di grup WhatsApp.\n"
    "- Sistem ini di-maintain secara volunteer oleh Vincent (vincent.koci.kusuma@gmail.com)"
)

WHATSAPP_ERROR_ALERT_TEMPLATE = (
    "[{timestamp}]\n\n"
    "WhatsApp API is unavailable.\n\n"
    "Error:\n\"{error_msg}\""
)