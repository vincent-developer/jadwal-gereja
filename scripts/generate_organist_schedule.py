import asyncio
import hashlib
import os
import sys
import random
from pathlib import Path
from string import capwords
import nest_asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from babel.dates import format_date
from dotenv import find_dotenv, load_dotenv
from typing import List, Any

# =======================================
# ENVIRONMENT SETUP & IMPORTS
# =======================================
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from config.settings import (
    MASTER_SPREADSHEET_ID,
    MASTER_SCHEDULE_SHEET_NAME,
    DATABASE_SPREADSHEET_ID,
    DATABASE_ORGANIST_SHEET_NAME,
    DATABASE_CHOIR_SHEET_NAME,
    DATABASE_LOG_SHEET_NAME,
    DATABASE_LOG_CHOIR_SHEET_NAME
)
from config.constants import (
    MONTH_MAP,
    LITURGICAL_YEAR_MAP,
    WEEKEND_DAYS,
    JAKARTA_TZ,
    REMINDER_HIGHLIGHT_FOOTER,
)
from services.gsheet_service import GoogleSheetsService
from utils.number import normalize_number
from utils.schedule_parse import parse_bapa_kami_version, parse_ordinarium_type
from utils.telegram_bot import TelegramBot
from utils.whatsapp_bot import (
    WhatsAppBot,
    WhatsAppNetworkError,
    WhatsAppAPIError
)
from models import Organist, Choir


load_dotenv(find_dotenv())


def skip_whatsapp() -> bool:
    """When true (env ``SKIP_WHATSAPP=1``), skip WhatsApp API checks and all WA sends."""
    return os.environ.get("SKIP_WHATSAPP", "").strip().lower() in ("1", "true", "yes")


# =======================================
# 1. HELPER FUNCTIONS
# =======================================


def get_first_advent(year: int) -> datetime:
    """Return the date of the first Advent Sunday for the given year."""
    dec_25 = datetime(year, 12, 25)
    days_to_sunday = dec_25.weekday() + 1
    return dec_25 - timedelta(days=days_to_sunday + 21)


def liturgical_year(date: datetime) -> str:
    """Determine the liturgical year (A, B, or C) based on Advent."""
    year = date.year
    first_advent = get_first_advent(year)
    lit_year = year + 1 if date >= first_advent else year
    return LITURGICAL_YEAR_MAP[lit_year % 3]  # ✅ Pakai dari constants


def _pad_row_to_len(row: list, length: int) -> list:
    """Right-pad a sheet row with empty strings up to ``length`` cells."""
    r = list(row)
    while len(r) < length:
        r.append("")
    return r[:length]


def _info_cell_text(info: Any) -> str:
    if info is None:
        return ""
    if isinstance(info, float) and pd.isna(info):
        return ""
    return str(info).strip()


def _optional_highlight_detail_line(label: str, value: Any) -> list[str]:
    """One ``Label: value`` line if value is non-empty; otherwise no lines."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    s = str(value).strip()
    if not s:
        return []
    return [f"{label}: {s}"]


def format_highlight_song_value(raw: str) -> str:
    """Display label for Ordinarium / Bapa Kami in highlight cards (e.g. ``ps 404`` -> ``PS 404``)."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.lower().startswith("ps "):
        return "PS " + s[3:].strip()
    return capwords(s)


def _jam_display(row: Any) -> str:
    j = row.get("Jam") if hasattr(row, "get") else getattr(row, "Jam", "")
    if j is None or (isinstance(j, float) and pd.isna(j)):
        return ""
    return str(j).strip()


def _datetime_parts(row: Any) -> tuple[str, str, str] | None:
    """Return (hari_id, tanggal_id, jam) from a schedule row, or None if date invalid."""
    dt = row["tgl-format"] if hasattr(row, "__getitem__") else row.get("tgl-format")
    if dt is None or (isinstance(dt, float) and pd.isna(dt)):
        return None
    hari = format_date(dt, "EEEE", locale="id")
    tanggal = format_date(dt, "d MMMM y", locale="id")
    return hari, tanggal, _jam_display(row)


def _highlight_date_line(hari: str, tanggal: str, jam: str) -> str:
    if jam:
        return f"📌 *{hari}, {tanggal} • {jam}*"
    return f"📌 *{hari}, {tanggal}*"


def _song_lines_from_info(info: Any) -> list[str]:
    """🎵 lines for the main highlight only (canonical values, display-formatted)."""
    text = _info_cell_text(info)
    if not text:
        return []
    ord_type = parse_ordinarium_type(text)
    bapa = parse_bapa_kami_version(text)
    out: list[str] = []
    if ord_type:
        out.append(f"🎵 Ordinarium: {format_highlight_song_value(ord_type)}")
    if bapa:
        out.append(f"🎵 Bapa Kami: {format_highlight_song_value(bapa)}")
    return out


def build_organist_highlight_reminder(name: str, next_three: Any) -> str:
    """
    WhatsApp/Telegram highlight card for organists: nearest schedule in full detail;
    at most two following lines without song details.
    """
    rows: list[Any] = [r for _, r in next_three.iterrows() if _datetime_parts(r) is not None]
    if not rows:
        return ""

    name_display = (name or "").strip().capitalize()
    lines: list[str] = [
        f"Hi {name_display}, berikut adalah detail jadwal organis kamu yang terdekat:",
        "",
    ]
    first = rows[0]
    hari, tanggal, jam = _datetime_parts(first)  # type: ignore[misc]
    koor_raw = str(first.get("Koor", "")).strip() or "-"
    koor_show = capwords(koor_raw) if koor_raw != "-" else "-"
    lines.append(_highlight_date_line(hari, tanggal, jam))
    lines.append(f"👥 Koor: {koor_show}")
    lines.extend(_optional_highlight_detail_line("Anamnesis", first.get("Anamnesis")))
    lines.extend(_optional_highlight_detail_line("Cara Tobat", first.get("Cara Tobat")))
    lines.extend(_song_lines_from_info(first.get("Info")))

    if len(rows) > 1:
        lines += ["", "*2 Jadwal Berikutnya:*"]
        upcoming: list[str] = []
        for r in rows[1:3]:
            parts = _datetime_parts(r)
            if not parts:
                continue
            h, t, j = parts
            k = str(r.get("Koor", "")).strip() or "-"
            k_disp = capwords(k) if k != "-" else "-"
            if j:
                upcoming.append(f"{h}, {t} • {j} (Koor: {k_disp})")
            else:
                upcoming.append(f"{h}, {t} (Koor: {k_disp})")
        lines.extend(f"• {u}" for u in upcoming)

    lines += ["", REMINDER_HIGHLIGHT_FOOTER]
    return "\n".join(lines)


def build_choir_highlight_reminder(
    coordinator_name: str,
    choir_name: str,
    next_three: Any,
) -> str:
    """
    WhatsApp/Telegram highlight card for choirs: nearest schedule in full detail;
    at most two following lines without song details.
    """
    rows: list[Any] = [r for _, r in next_three.iterrows() if _datetime_parts(r) is not None]
    if not rows:
        return ""

    coord_display = (coordinator_name or "Koordinator").strip().capitalize()
    choir_display = capwords((choir_name or "").strip())
    lines: list[str] = [
        f"Hi {coord_display}, berikut adalah detail jadwal pelayanan *{choir_display}* yang terdekat:",
        "",
    ]
    first = rows[0]
    hari, tanggal, jam = _datetime_parts(first)  # type: ignore[misc]
    org_raw = str(first.get("Organis", "")).strip() or "-"
    org_show = org_raw if org_raw == "-" else capwords(org_raw)
    lines.append(_highlight_date_line(hari, tanggal, jam))
    lines.append(f"🎹 Organis: {org_show}")
    lines.extend(_optional_highlight_detail_line("Anamnesis", first.get("Anamnesis")))
    lines.extend(_optional_highlight_detail_line("Cara Tobat", first.get("Cara Tobat")))
    lines.extend(_song_lines_from_info(first.get("Info")))

    if len(rows) > 1:
        lines += ["", "*2 Jadwal Berikutnya:*"]
        upcoming: list[str] = []
        for r in rows[1:3]:
            parts = _datetime_parts(r)
            if not parts:
                continue
            h, t, j = parts
            o = str(r.get("Organis", "")).strip() or "-"
            o_disp = o if o == "-" else capwords(o)
            if j:
                upcoming.append(f"{h}, {t} • {j} (Organis: {o_disp})")
            else:
                upcoming.append(f"{h}, {t} (Organis: {o_disp})")
        lines.extend(f"• {u}" for u in upcoming)

    lines += ["", REMINDER_HIGHLIGHT_FOOTER]
    return "\n".join(lines)


def reminder_message_hash(reminder_text: str) -> str:
    """Stable hash for log deduplication when message body changes."""
    return hashlib.sha256(reminder_text.encode("utf-8")).hexdigest()


def is_number_match(stored_number: str, input_number: str, platform: str) -> bool:
    """Check if stored number matches input number based on platform."""
    if platform == "telegram":
        return str(stored_number).strip() == str(input_number).strip()
    else:
        return (
            str(normalize_number(stored_number)).strip()
            == str(normalize_number(input_number)).strip()
        )


_LOG_ORGANIST_HEADERS = ["Timestamp", "Name", "Chat Id / Whatsapp No", "Message Preview", "Schedule Hash", "Status", "Platform"]
_LOG_CHOIR_HEADERS = ["Timestamp", "Koor", "Nama Koordinator", "Whatsapp No", "Message Preview", "Schedule Hash", "Status"]


def _load_log_sheet(gsheet: GoogleSheetsService, spreadsheet_id: str, sheet_name: str, headers: list) -> list:
    """Load all records from a log sheet, creating it with headers if it does not exist."""
    try:
        return gsheet.read_all_records(spreadsheet_id, sheet_name)
    except:
        gsheet.get_or_create_worksheet(spreadsheet_id, sheet_name, rows=10, cols=7)
        gsheet.append_row(spreadsheet_id, sheet_name, headers)
        return []


def read_last_log(
    gsheet: GoogleSheetsService,
    spreadsheet_id: str,
    id: str,
    platform: str,
    records: list | None = None,
) -> dict | None:
    """
    Return last matching log entry based on chat_id AND platform.
    Pass pre-loaded `records` to skip the sheet read (avoids redundant API call).
    """
    if records is None:
        records = _load_log_sheet(gsheet, spreadsheet_id, DATABASE_LOG_SHEET_NAME, _LOG_ORGANIST_HEADERS)

    for row in reversed(records):
        if is_number_match(
            row.get("Chat Id / Whatsapp No", ""), id, platform
        ) and str(row.get("Platform", "")).strip().lower() == platform.strip().lower():
            return row

    return None


def update_log(
    gsheet: GoogleSheetsService,
    spreadsheet_id: str,
    name: str,
    id: str,
    preview: str,
    hash_value: str,
    status: str,
    platform: str,
    records: list | None = None,
    pending_writes: list | None = None,
) -> list:
    """
    Update or insert log entry. Pass pre-loaded `records` to skip re-reading the sheet.
    Pass `pending_writes` list to defer the actual write — caller must call flush_log_writes() after the loop.
    Returns the updated records list so the caller's in-memory cache stays in sync.
    """
    SHEET_NAME = DATABASE_LOG_SHEET_NAME

    if records is None:
        records = _load_log_sheet(gsheet, spreadsheet_id, SHEET_NAME, _LOG_ORGANIST_HEADERS)

    timestamp = datetime.now(ZoneInfo(JAKARTA_TZ)).strftime("%Y-%m-%d %H:%M:%S")
    normalized_id = id if platform == "telegram" else normalize_number(id)
    new_values = [timestamp, name, normalized_id, preview, hash_value, status, platform]

    # Search existing row
    for idx, row in enumerate(records, start=2):
        if is_number_match(
            row.get("Chat Id / Whatsapp No"), id, platform
        ) and str(row.get("Platform")).strip().lower() == platform.strip().lower():
            if pending_writes is not None:
                pending_writes.append({"type": "update", "row": idx, "values": new_values})
            else:
                gsheet.update_row(spreadsheet_id, SHEET_NAME, idx, new_values)
            records[idx - 2] = dict(zip(_LOG_ORGANIST_HEADERS, new_values))
            return records

    if pending_writes is not None:
        pending_writes.append({"type": "append", "values": new_values})
    else:
        gsheet.append_row(spreadsheet_id, SHEET_NAME, new_values)
    records.append(dict(zip(_LOG_ORGANIST_HEADERS, new_values)))
    return records

def read_last_choir_log(
    gsheet: GoogleSheetsService,
    spreadsheet_id: str,
    whatsapp_no: str,
    choir_name: str,
    records: list | None = None,
) -> dict | None:
    """
    Return last matching choir log entry based on whatsapp_no AND choir_name (composite key).
    Pass pre-loaded `records` to skip the sheet read (avoids redundant API call).
    """
    if records is None:
        records = _load_log_sheet(gsheet, spreadsheet_id, DATABASE_LOG_CHOIR_SHEET_NAME, _LOG_CHOIR_HEADERS)

    # Search from bottom to get the latest entry matching BOTH whatsapp_no AND choir_name
    for row in reversed(records):
        if (is_number_match(row.get("Whatsapp No", ""), whatsapp_no, "whatsapp") and
                str(row.get("Koor", "")).strip().lower() == choir_name.strip().lower()):
            return row

    return None


def update_choir_log(
    gsheet: GoogleSheetsService,
    spreadsheet_id: str,
    koor: str,
    nama_koordinator: str,
    whatsapp_no: str,
    preview: str,
    hash_value: str,
    status: str,
    records: list | None = None,
    pending_writes: list | None = None,
) -> list:
    """
    Update or insert choir log entry. Pass pre-loaded `records` to skip re-reading the sheet.
    Pass `pending_writes` list to defer the actual write — caller must call flush_log_writes() after the loop.
    Returns the updated records list so the caller's in-memory cache stays in sync.
    """
    SHEET_NAME = DATABASE_LOG_CHOIR_SHEET_NAME

    if records is None:
        records = _load_log_sheet(gsheet, spreadsheet_id, SHEET_NAME, _LOG_CHOIR_HEADERS)

    timestamp = datetime.now(ZoneInfo(JAKARTA_TZ)).strftime("%Y-%m-%d %H:%M:%S")
    new_values = [timestamp, koor, nama_koordinator, normalize_number(whatsapp_no), preview, hash_value, status]

    # Search existing row matching BOTH whatsapp_no AND choir_name
    for idx, row in enumerate(records, start=2):
        if (is_number_match(row.get("Whatsapp No"), whatsapp_no, "whatsapp") and
                str(row.get("Koor", "")).strip().lower() == koor.strip().lower()):
            if pending_writes is not None:
                pending_writes.append({"type": "update", "row": idx, "values": new_values})
            else:
                gsheet.update_row(spreadsheet_id, SHEET_NAME, idx, new_values)
            records[idx - 2] = dict(zip(_LOG_CHOIR_HEADERS, new_values))
            return records

    if pending_writes is not None:
        pending_writes.append({"type": "append", "values": new_values})
    else:
        gsheet.append_row(spreadsheet_id, SHEET_NAME, new_values)
    records.append(dict(zip(_LOG_CHOIR_HEADERS, new_values)))
    return records



# Initialize Google Sheets Service
gsheet = GoogleSheetsService()

# =======================================
# LOAD ORGANIST LIST
# =======================================
all_organist_data = gsheet.read_all_values(DATABASE_SPREADSHEET_ID, DATABASE_ORGANIST_SHEET_NAME)
organists: List[Organist] = []

# 3. Loop data (skip header)
for row in all_organist_data[1:]:
    # Skip baris kosong atau tanpa nama
    if not row or not row[0].strip():
        continue
    
    # Extract data (Logic Anda yang sudah aman)
    name = row[0].strip()
    
    # Ambil chat_id (cek index bounds dan empty string)
    raw_chat_id = row[1].strip() if len(row) > 1 else ""
    chat_id = raw_chat_id if raw_chat_id else None
    
    # Ambil wa_number
    raw_wa = row[2].strip() if len(row) > 2 else ""
    wa_number = raw_wa if raw_wa else None

    # --- PERUBAHAN UTAMA DI SINI ---
    # Buat object Organist, bukan dictionary
    new_organist = Organist(
        name=name,
        telegram_chat_id=chat_id,
        wa_number=wa_number
    )
    organists.append(new_organist)
    
    
    
    
# =======================================
# LOAD CHOIR LIST
# =======================================
all_choir_data = gsheet.read_all_values(DATABASE_SPREADSHEET_ID, DATABASE_CHOIR_SHEET_NAME)
choirs: List[Choir] = []

# 3. Loop data (skip header)
for row in all_choir_data[1:]:
    # Skip baris kosong atau tanpa nama
    if not row or not row[0].strip():
        continue
    
    choir_name = row[0].strip()
    
    raw_wa = row[1].strip() if len(row) > 1 else ""
    wa_number = raw_wa if raw_wa else None
    
    raw_coord_name = row[2].strip() if len(row) > 2 else ""
    coordinator_name = raw_coord_name if raw_coord_name else None
    
    new_choir = Choir(
        choir_name=choir_name,
        wa_number=wa_number,
        coordinator_name=coordinator_name
    )
    choirs.append(new_choir)
    
    

# =======================================
# 4. LOAD & PREPROCESS DATA
# =======================================
all_data = gsheet.read_all_values(MASTER_SPREADSHEET_ID, MASTER_SCHEDULE_SHEET_NAME)  # ✅ Pakai dari settings

# Extract main data columns A–K (A = liturgy info for schedule_parse; B–K as before)
data = []
for row in all_data[4:]:
    if len(row) < 10:
        continue
    data.append(_pad_row_to_len(row, 11))

_df_cols = ["Info", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]
df = pd.DataFrame(data, columns=_df_cols).copy()

# Override columns F,G if J,K are filled
mask_j = df["J"].astype(str).str.strip() != ""
df.loc[mask_j, ["F", "G"]] = df.loc[mask_j, ["J", "K"]].values
# cleaning unused field
df = df[["Info", "B", "C", "D", "E", "F", "G"]]


target_date = datetime(datetime.now().year, 12, 25)
today = datetime.now()
if today < target_date:
    # Extract extra data (second schedule section)
    data_extra = [row[14:18] for row in all_data[4:982] if len(row) >= 18]
    df_extra = pd.DataFrame(data_extra, columns=["O", "P", "Q", "R"])
    df_extra["B"], df_extra["C"], df_extra["F"], df_extra["G"] = df_extra["O"], df_extra["P"], df_extra["Q"], df_extra["R"]
    df_extra["D"], df_extra["E"] = "", ""
    df_extra["Info"] = ""
    df_extra = df_extra[["Info", "B", "C", "D", "E", "F", "G"]]

    # Merge both sections
    df_all = pd.concat([df, df_extra], ignore_index=True)
else:
    df_all = df


# Convert dates
# ✅ Pakai MONTH_MAP dari constants
b_str = df_all["B"].astype(str).str.strip().replace(MONTH_MAP, regex=True)
b_dt = pd.to_datetime(b_str, dayfirst=True, errors="coerce")

# Handle Excel serial date format
serial_mask = b_str.str.match(r"^\d{4,6}$", na=False)
b_dt.loc[serial_mask] = pd.to_datetime("1899-12-30") + pd.to_timedelta(
    b_str.loc[serial_mask].astype(int), unit="D"
)

df_all["B_dt"] = b_dt
today_jkt = datetime.now(ZoneInfo(JAKARTA_TZ)).date()  # ✅ Pakai dari settings
df_all = (
    df_all[df_all["B_dt"].dt.date >= today_jkt]
    .copy()
    .sort_values("B_dt")
    .reset_index(drop=True)
)

# Clean and standardize columns
df_clean = df_all[["Info", "B", "C", "D", "E", "F", "G", "B_dt"]].copy()
df_clean.columns = [
    "Info",
    "Tanggal",
    "Jam",
    "Anamnesis",
    "Cara Tobat",
    "Koor",
    "Organis",
    "tgl-format",
]
df_clean["Tahun Liturgi"] = df_clean["tgl-format"].apply(liturgical_year)

# Format day name (Indonesian)
df_clean["Hari"] = df_clean["tgl-format"].apply(
    lambda d: format_date(d, "EEEE", locale="id") if pd.notnull(d) else ""
)
df_clean["Weekday"] = df_clean["Hari"].apply(
    lambda x: "yes" if x not in WEEKEND_DAYS else "no"  # ✅ Pakai dari constants
)

# =======================================
# REMINDER SENDER
# =======================================

async def send_organist_notification_reminders():
    print("🚀 Starting organist reminder process...\n", flush=True)

    # Load organist log sheet once — reused across all organists (no repeated reads)
    log_records = _load_log_sheet(
        gsheet, DATABASE_SPREADSHEET_ID, DATABASE_LOG_SHEET_NAME, _LOG_ORGANIST_HEADERS
    )
    pending_writes: list = []  # deferred log writes, flushed in one batch after loop

    for rec in organists:
        name = rec.name
        chat_id = rec.telegram_chat_id  # Perhatikan nama field sesuai definisi Class
        wa_number = rec.wa_number
        has_telegram = rec.has_telegram()
        has_whatsapp = rec.has_whatsapp()
        print(f"🔹 Processing {name}...", flush=True)

        # Filter schedule
        filter_df = df_clean[df_clean["Organis"].str.lower() == name.lower()].copy()

        # Drop the 'tgl-format' column before saving
        df_to_save = filter_df.drop(columns=["tgl-format"])

        # Reorder the table
        new_order = [
            "Hari",
            "Tanggal",
            "Jam",
            "Info",
            "Anamnesis",
            "Cara Tobat",
            "Koor",
            "Organis",
            "Tahun Liturgi",
            "Weekday",
        ]
        df_to_save = df_to_save[new_order]

        await asyncio.to_thread(
            gsheet.save_dataframe,
            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
            f"Jadwal {name.capitalize()}",
            df_to_save
        )

        # Send notifications if schedule exists
        if not filter_df.empty:
            next_three = filter_df.head(3).copy()
            next_three["Tanggal_dt"] = next_three["tgl-format"]

            reminder_text = build_organist_highlight_reminder(name, next_three)
            if not reminder_text:
                print(f"⚠️ Skipping notifications for {name}: no valid schedule dates.", flush=True)
            else:
                print(reminder_text, flush=True)
                print("=" * 60, flush=True)

                hash_value = reminder_message_hash(reminder_text)

                # Notification by WhatsApp
                if has_whatsapp and not skip_whatsapp():
                    previous_log = read_last_log(
                        gsheet, DATABASE_SPREADSHEET_ID, id=wa_number, platform="whatsapp",
                        records=log_records
                    )

                    if previous_log and previous_log.get("Schedule Hash") == hash_value:
                        # Same schedule → skip sending
                        print(f"⏭ SKIPPED (duplicate schedule): {name}", flush=True)
                        log_records = update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,
                            name,
                            id=wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="skipped",
                            platform="whatsapp",
                            records=log_records,
                            pending_writes=pending_writes,
                        )
                    else:
                        try:
                            whatsAppBot = WhatsAppBot()
                            whatsAppBot.send(wa_number, reminder_text)
                            print(
                                f"📨 Whatsapp Reminder sent to {name} ({wa_number})",
                                flush=True,
                            )
                            log_records = update_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                name,
                                id=wa_number,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status="sent",
                                platform="whatsapp",
                                records=log_records,
                                pending_writes=pending_writes,
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to send Whatsapp to {name}: {e}", flush=True)
                            log_records = update_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                name,
                                id=wa_number,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status=f"error: {e}",
                                platform="whatsapp",
                                records=log_records,
                                pending_writes=pending_writes,
                            )

                # Notification by Telegram
                if has_telegram:
                    previous_log = read_last_log(
                        gsheet, DATABASE_SPREADSHEET_ID, id=chat_id, platform="telegram",
                        records=log_records
                    )

                    if previous_log and previous_log.get("Schedule Hash") == hash_value:
                        # Same schedule → skip sending
                        print(f"⏭ SKIPPED (duplicate schedule): {name}", flush=True)
                        log_records = update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,
                            name,
                            id=chat_id,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="skipped",
                            platform="telegram",
                            records=log_records,
                            pending_writes=pending_writes,
                        )
                    else:
                        try:
                            telegramBot = TelegramBot(chat_id=chat_id)
                            await telegramBot.send(reminder_text)
                            print(f"📨 Reminder sent to {name} ({chat_id})", flush=True)
                            log_records = update_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                name,
                                id=chat_id,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status="sent",
                                platform="telegram",
                                records=log_records,
                                pending_writes=pending_writes,
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to send Telegram to {name}: {e}", flush=True)
                            log_records = update_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                name,
                                id=chat_id,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status=f"error: {e}",
                                platform="telegram",
                                records=log_records,
                                pending_writes=pending_writes,
                            )
        await asyncio.sleep(random.uniform(6, 15))

    # Flush all log writes in one batch after the full loop
    gsheet.flush_log_writes(DATABASE_SPREADSHEET_ID, DATABASE_LOG_SHEET_NAME, pending_writes)
    print("\n✅ All reminders processed!", flush=True)


async def send_choir_notification_reminders():
    print("🚀 Starting Choir reminder process...\n", flush=True)

    # Load choir log sheet once — reused across all choirs (no repeated reads)
    choir_log_records = _load_log_sheet(
        gsheet, DATABASE_SPREADSHEET_ID, DATABASE_LOG_CHOIR_SHEET_NAME, _LOG_CHOIR_HEADERS
    )
    choir_pending_writes: list = []  # deferred log writes, flushed in one batch after loop

    for rec in choirs:
        print(f"🔹 Processing {rec.choir_name}...", flush=True)

        # Filter schedule
        filter_df = df_clean[df_clean["Koor"].str.lower() == rec.choir_name.lower()].copy()

        # Send notifications if schedule exists
        if not filter_df.empty:
            next_three = filter_df.head(3).copy()
            next_three["Tanggal_dt"] = next_three["tgl-format"]

            reminder_text = build_choir_highlight_reminder(
                rec.coordinator_name or "Koordinator",
                rec.choir_name,
                next_three,
            )
            if not reminder_text:
                print(
                    f"⚠️ Skipping notifications for {rec.choir_name}: no valid schedule dates.",
                    flush=True,
                )
            else:
                print(reminder_text, flush=True)
                print("=" * 60, flush=True)

                hash_value = reminder_message_hash(reminder_text)

                # Notification by WhatsApp
                if rec.has_whatsapp() and not skip_whatsapp():
                    previous_log = read_last_choir_log(
                        gsheet, DATABASE_SPREADSHEET_ID, rec.wa_number, rec.choir_name,
                        records=choir_log_records
                    )

                    if previous_log and previous_log.get("Schedule Hash") == hash_value:
                        # Same schedule → skip sending
                        print(f"⏭ SKIPPED (duplicate schedule): {rec.choir_name}", flush=True)
                        choir_log_records = update_choir_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,
                            rec.choir_name,
                            rec.coordinator_name,
                            rec.wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="skipped",
                            records=choir_log_records,
                            pending_writes=choir_pending_writes,
                        )
                    else:
                        try:
                            whatsAppBot = WhatsAppBot()
                            whatsAppBot.send(rec.wa_number, reminder_text)
                            print(
                                f"📨 Whatsapp Reminder sent to {rec.choir_name} ({rec.wa_number})",
                                flush=True,
                            )
                            choir_log_records = update_choir_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                rec.choir_name,
                                rec.coordinator_name,
                                rec.wa_number,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status="sent",
                                records=choir_log_records,
                                pending_writes=choir_pending_writes,
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to send Whatsapp to {rec.choir_name}: {e}", flush=True)
                            choir_log_records = update_choir_log(
                                gsheet,
                                DATABASE_SPREADSHEET_ID,
                                rec.choir_name,
                                rec.coordinator_name,
                                rec.wa_number,
                                preview=reminder_text[:100],
                                hash_value=hash_value,
                                status=f"error: {e}",
                                records=choir_log_records,
                                pending_writes=choir_pending_writes,
                            )
        await asyncio.sleep(random.uniform(6, 15))

    # Flush all choir log writes in one batch after the full loop
    gsheet.flush_log_writes(DATABASE_SPREADSHEET_ID, DATABASE_LOG_CHOIR_SHEET_NAME, choir_pending_writes)
    print("\n✅ All choir reminders processed!", flush=True)



async def check_and_run():
    admin_chat_id = "1731149425"

    if skip_whatsapp():
        print(
            "SKIP_WHATSAPP is set: skipping WhatsApp health check and all WhatsApp sends.",
            flush=True,
        )
        await send_organist_notification_reminders()
        await send_choir_notification_reminders()
        return

    whatsAppBot = WhatsAppBot()

    print("Checking WhatsApp connection status...")
    
    error_msg = None
    try:
        status = whatsAppBot.get_status()
        
        # Check if the 'connected' field is True
        if status.get("connected") is True:
            print("WhatsApp READY. Starting notifications...")
            # Proceed to the main function
            await send_organist_notification_reminders()
            await send_choir_notification_reminders()
            return 
        else:
            # Capture specific status from API if not connected
            error_msg = status.get('whatsapp_status', 'NOT CONNECTED')
            print(f"WhatsApp status is: {error_msg}")

    except (WhatsAppNetworkError, WhatsAppAPIError) as e:
        error_msg = str(e)
    except Exception as e:
        error_msg = f"Unexpected Error: {str(e)}"

    # If error_msg exists, send Telegram alert and stop execution
    if error_msg:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        reminder_text = (
            f"[{timestamp}]\n\n"
            f"WhatsApp API is unavailable.\n\n"
            f"Error:\n\"{error_msg}\""
        )
        
        print("Sending alert to Telegram...")
        try:
            telegramBot = TelegramBot(chat_id=admin_chat_id)
            await telegramBot.send(reminder_text)
            print("Telegram alert sent.")
        except Exception as tel_err:
            print(f"Failed to send Telegram: {tel_err}")
        
        print("System halted.")
        
        # SAFE EXIT LOGIC:
        # Check if running in Jupyter (ipykernel) or standard Python
        if 'ipykernel' in sys.modules:
            # In Jupyter, return quietly to avoid messy red error boxes
            return 
        else:
            # In a .py script, exit with status 1 for system signaling
            sys.exit(1)


# =======================================
# 6. RUN MAIN FUNCTION
# =======================================
if __name__ == "__main__":   
    nest_asyncio.apply()
    asyncio.run(check_and_run())