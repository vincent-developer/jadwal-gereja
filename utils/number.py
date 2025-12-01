import re

# ---------- Number Normalization ----------
def normalize_number(num: str) -> str:
    """Normalize phone numbers to simplified E.164 format (+62...)."""
    if not num:
        return ""
    s = re.sub(r"[^\d+]", "", str(num))
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    if s.startswith("+"):
        return "+" + digits
    if digits.startswith("0"):
        return "+62" + digits[1:]
    if digits.startswith("62"):
        return "+" + digits
    if digits.startswith("8"):
        return "+62" + digits
    return "+" + digits