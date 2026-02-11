import asyncio
import sys
import random
import nest_asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from babel.dates import format_date
from dotenv import find_dotenv, load_dotenv
from typing import List

# =======================================
# ENVIRONMENT SETUP & IMPORTS
# =======================================
sys.path.append("..")
from config.settings import (
    MASTER_SPREADSHEET_ID,
    MASTER_SCHEDULE_SHEET_NAME,
    DATABASE_SPREADSHEET_ID,
    DATABASE_ORGANIST_SHEET_NAME,
    DATABASE_CHOIR_SHEET_NAME,
    DATABASE_LOG_SHEET_NAME,
    DATABASE_LOG_CHOIR_SHEET_NAME
)
from config.constants import MONTH_MAP, LITURGICAL_YEAR_MAP, WEEKEND_DAYS, JAKARTA_TZ, REMINDER_MESSAGE_TEMPLATE, REMINDER_MESSAGE_TEMPLATE_CHOIR
from services.gsheet_service import GoogleSheetsService
from utils.number import normalize_number
from utils.telegram_bot import TelegramBot
from utils.whatsapp_bot import (
    WhatsAppBot,
    WhatsAppNetworkError,
    WhatsAppAPIError
)
from models import Organist, Choir


load_dotenv(find_dotenv())

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


def is_number_match(stored_number: str, input_number: str, platform: str) -> bool:
    """Check if stored number matches input number based on platform."""
    if platform == "telegram":
        return str(stored_number).strip() == str(input_number).strip()
    else:
        return (
            str(normalize_number(stored_number)).strip()
            == str(normalize_number(input_number)).strip()
        )


def read_last_log(gsheet: GoogleSheetsService, spreadsheet_id: str, id: str, platform: str) -> dict | None:
    """
    Return last matching log entry based on chat_id AND platform.
    If no match found, return None. If sheet not found, create and return None.
    """
    SHEET_NAME = DATABASE_LOG_SHEET_NAME

    try:
        records = gsheet.read_all_records(spreadsheet_id, SHEET_NAME)

        # Search from bottom to get the latest entry
        for row in reversed(records):
            if is_number_match(
                row.get("Chat Id / Whatsapp No", ""), id, platform
            ) and str(row.get("Platform", "")).strip().lower() == platform.strip().lower():
                return row

        return None

    except:
        # Sheet doesn't exist → create new one
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
        gsheet.append_row(
            spreadsheet_id,
            SHEET_NAME,
            [
                "Timestamp",
                "Name",
                "Chat Id / Whatsapp No",
                "Message Preview",
                "Schedule Hash",
                "Status",
                "Platform",
            ]
        )
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
) -> None:
    """Update or insert log entry ensuring only one record exists per id and platform."""
    SHEET_NAME = DATABASE_LOG_SHEET_NAME

    try:
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
    except:
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
        gsheet.append_row(
            spreadsheet_id,
            SHEET_NAME,
            [
                "Timestamp",
                "Name",
                "Chat Id / Whatsapp No",
                "Message Preview",
                "Schedule Hash",
                "Status",
                "Platform",
            ]
        )

    records = gsheet.read_all_records(spreadsheet_id, SHEET_NAME)
    timestamp = datetime.now(ZoneInfo(JAKARTA_TZ)).strftime("%Y-%m-%d %H:%M:%S")  # ✅ Pakai dari settings

    # Search existing row
    for idx, row in enumerate(records, start=2):
        if is_number_match(
            row.get("Chat Id / Whatsapp No"), id, platform
        ) and str(row.get("Platform")).strip().lower() == platform.strip().lower():
            gsheet.update_row(
                spreadsheet_id,
                SHEET_NAME,
                idx,
                [timestamp, name, id if platform == "telegram" else normalize_number(id), preview, hash_value, status, platform]
            )
            return

    # Insert new row if none found
    gsheet.append_row(
        spreadsheet_id,
        SHEET_NAME,
        [
            timestamp,
            name,
            id if platform == "telegram" else normalize_number(id),
            preview,
            hash_value,
            status,
            platform,
        ]
    )

def read_last_choir_log(gsheet: GoogleSheetsService, spreadsheet_id: str, whatsapp_no: str, choir_name: str) -> dict | None:
    """
    Return last matching choir log entry based on whatsapp_no AND choir_name (composite key).
    If no match found, return None. If sheet not found, create and return None.
    """
    SHEET_NAME = DATABASE_LOG_CHOIR_SHEET_NAME

    try:
        records = gsheet.read_all_records(spreadsheet_id, SHEET_NAME)

        # Search from bottom to get the latest entry matching BOTH whatsapp_no AND choir_name
        for row in reversed(records):
            if (is_number_match(row.get("Whatsapp No", ""), whatsapp_no, "whatsapp") and 
                str(row.get("Koor", "")).strip().lower() == choir_name.strip().lower()):
                return row

        return None

    except:
        # Sheet doesn't exist → create new one
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
        gsheet.append_row(
            spreadsheet_id,
            SHEET_NAME,
            [
                "Timestamp",
                "Koor",
                "Nama Koordinator",
                "Whatsapp No",
                "Message Preview",
                "Schedule Hash",
                "Status",
            ]
        )
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
) -> None:
    """Update or insert choir log entry ensuring only one record exists per (whatsapp_no, choir_name) composite key."""
    SHEET_NAME = DATABASE_LOG_CHOIR_SHEET_NAME

    try:
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
    except:
        gsheet.get_or_create_worksheet(spreadsheet_id, SHEET_NAME, rows=10, cols=7)
        gsheet.append_row(
            spreadsheet_id,
            SHEET_NAME,
            [
                "Timestamp",
                "Koor",
                "Nama Koordinator",
                "Whatsapp No",
                "Message Preview",
                "Schedule Hash",
                "Status",
            ]
        )

    records = gsheet.read_all_records(spreadsheet_id, SHEET_NAME)
    timestamp = datetime.now(ZoneInfo(JAKARTA_TZ)).strftime("%Y-%m-%d %H:%M:%S")

    # Search existing row matching BOTH whatsapp_no AND choir_name
    for idx, row in enumerate(records, start=2):
        if (is_number_match(row.get("Whatsapp No"), whatsapp_no, "whatsapp") and
            str(row.get("Koor", "")).strip().lower() == koor.strip().lower()):
            gsheet.update_row(
                spreadsheet_id,
                SHEET_NAME,
                idx,
                [timestamp, koor, nama_koordinator, normalize_number(whatsapp_no), preview, hash_value, status]
            )
            return

    # Insert new row if none found
    gsheet.append_row(
        spreadsheet_id,
        SHEET_NAME,
        [
            timestamp,
            koor,
            nama_koordinator,
            normalize_number(whatsapp_no),
            preview,
            hash_value,
            status,
        ]
    )



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

# Extract main data columns
data = [row[1:11] for row in all_data[4:] if len(row) >= 11]
df = pd.DataFrame(data, columns=["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]).copy()

# Override columns F,G if J,K are filled
mask_j = df["J"].astype(str).str.strip() != ""
df.loc[mask_j, ["F", "G"]] = df.loc[mask_j, ["J", "K"]].values
# cleaning unused field
df = df[["B", "C", "D", "E", "F", "G"]]


target_date = datetime(datetime.now().year, 12, 25)
today = datetime.now()
if today < target_date:
    # Extract extra data (second schedule section)
    data_extra = [row[14:18] for row in all_data[4:982] if len(row) >= 18]
    df_extra = pd.DataFrame(data_extra, columns=["O", "P", "Q", "R"])
    df_extra["B"], df_extra["C"], df_extra["F"], df_extra["G"] = df_extra["O"], df_extra["P"], df_extra["Q"], df_extra["R"]
    df_extra["D"], df_extra["E"] = "", ""
    df_extra = df_extra[["B", "C", "D", "E", "F", "G"]]

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
df_clean = df_all[["B", "C", "D", "E", "F", "G", "B_dt"]].copy()
df_clean.columns = [
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

            tanggal_list = []
            for _, row in next_three.iterrows():
                if pd.notnull(row["Tanggal_dt"]):
                    hari = format_date(row["Tanggal_dt"], "EEEE", locale="id")
                    tanggal = format_date(row["Tanggal_dt"], "d MMMM y", locale="id")
                    jam = str(row["Jam"]).strip() if pd.notnull(row["Jam"]) else ""
                    koor = str(row["Koor"]).strip() if pd.notnull(row["Koor"]) else "-"
                    tanggal_list.append(f"- {hari}, {tanggal} • {jam} (Koor: {koor})")

            schedule_string = "\n".join(tanggal_list)

            reminder_text = REMINDER_MESSAGE_TEMPLATE.format(
                name=name.capitalize(),  
                schedule_list=schedule_string 
            )

            print(reminder_text, flush=True)
            print("=" * 60, flush=True)

            # Create schedule hash based on dates & times
            hash_value = "|".join(tanggal_list)

            # Notification by WhatsApp
            if has_whatsapp:
                previous_log = read_last_log(
                    gsheet, DATABASE_SPREADSHEET_ID, id=wa_number, platform="whatsapp"  # ✅ Pakai dari settings
                )

                if previous_log and previous_log.get("Schedule Hash") == hash_value:
                    # Same schedule → skip sending
                    print(f"⏭ SKIPPED (duplicate schedule): {name}", flush=True)
                    update_log(
                        gsheet,
                        DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                        name,
                        id=wa_number,
                        preview=reminder_text[:100],
                        hash_value=hash_value,
                        status="skipped",
                        platform="whatsapp",
                    )
                else:
                    try:
                        whatsAppBot = WhatsAppBot()
                        whatsAppBot.send(wa_number, reminder_text)
                        print(
                            f"📨 Whatsapp Reminder sent to {name} ({wa_number})",
                            flush=True,
                        )
                        update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            name,
                            id=wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="sent",
                            platform="whatsapp",
                        )
                    except Exception as e:
                        print(f"⚠️ Failed to send Whatsapp to {name}: {e}", flush=True)
                        update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            name,
                            id=wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status=f"error: {e}",
                            platform="whatsapp",
                        )

            # Notification by Telegram
            if has_telegram:
                previous_log = read_last_log(
                    gsheet, DATABASE_SPREADSHEET_ID, id=chat_id, platform="telegram"  # ✅ Pakai dari settings
                )

                if previous_log and previous_log.get("Schedule Hash") == hash_value:
                    # Same schedule → skip sending
                    print(f"⏭ SKIPPED (duplicate schedule): {name}", flush=True)
                    update_log(
                        gsheet,
                        DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                        name,
                        id=chat_id,
                        preview=reminder_text[:100],
                        hash_value=hash_value,
                        status="skipped",
                        platform="telegram",
                    )
                else:
                    try:
                        telegramBot = TelegramBot(chat_id=chat_id)
                        await telegramBot.send(reminder_text)
                        print(f"📨 Reminder sent to {name} ({chat_id})", flush=True)
                        update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            name,
                            id=chat_id,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="sent",
                            platform="telegram",
                        )
                    except Exception as e:
                        print(f"⚠️ Failed to send Telegram to {name}: {e}", flush=True)
                        update_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            name,
                            id=chat_id,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status=f"error: {e}",
                            platform="telegram",
                        )
        await asyncio.sleep(random.uniform(6, 15))

    print("\n✅ All reminders processed!", flush=True)


async def send_choir_notification_reminders():
    print("🚀 Starting Choir reminder process...\n", flush=True)

    for rec in choirs:
        print(f"🔹 Processing {rec.choir_name}...", flush=True)

        # Filter schedule
        filter_df = df_clean[df_clean["Koor"].str.lower() == rec.choir_name.lower()].copy()

        # Send notifications if schedule exists
        if not filter_df.empty:
            next_three = filter_df.head(3).copy()
            next_three["Tanggal_dt"] = next_three["tgl-format"]

            tanggal_list = []
            for _, row in next_three.iterrows():
                if pd.notnull(row["Tanggal_dt"]):
                    hari = format_date(row["Tanggal_dt"], "EEEE", locale="id")
                    tanggal = format_date(row["Tanggal_dt"], "d MMMM y", locale="id")
                    jam = str(row["Jam"]).strip() if pd.notnull(row["Jam"]) else ""
                    organist = str(row["Organis"]).strip() if pd.notnull(row["Organis"]) else "-"
                    tanggal_list.append(f"- {hari}, {tanggal} • {jam} (Organist: {organist})")

            schedule_string = "\n".join(tanggal_list)

            reminder_text = REMINDER_MESSAGE_TEMPLATE_CHOIR.format(
                coord_name=(rec.coordinator_name or "Koordinator").capitalize(),  
                choir_name=rec.choir_name.capitalize(),
                schedule_list=schedule_string 
            )

            print(reminder_text, flush=True)
            print("=" * 60, flush=True)

            # Create schedule hash based on dates & times
            hash_value = "|".join(tanggal_list)

            # Notification by WhatsApp
            if rec.has_whatsapp():
                previous_log = read_last_choir_log(
                    gsheet, DATABASE_SPREADSHEET_ID, rec.wa_number, rec.choir_name
                )

                if previous_log and previous_log.get("Schedule Hash") == hash_value:
                    # Same schedule → skip sending
                    print(f"⏭ SKIPPED (duplicate schedule): {rec.choir_name}", flush=True)
                    
                    update_choir_log(
                        gsheet,
                        DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                        rec.choir_name,
                        rec.coordinator_name,
                        rec.wa_number,
                        preview=reminder_text[:100],
                        hash_value=hash_value,
                        status="skipped",
                    )
                else:
                    try:
                        whatsAppBot = WhatsAppBot()
                        whatsAppBot.send(rec.wa_number, reminder_text)
                        print(
                            f"📨 Whatsapp Reminder sent to {rec.choir_name} ({rec.wa_number})",
                            flush=True,
                        )
                        
                        update_choir_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            rec.choir_name,
                            rec.coordinator_name,
                            rec.wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status="sent",
                        )
                    except Exception as e:
                        print(f"⚠️ Failed to send Whatsapp to {rec.choir_name}: {e}", flush=True)
                        update_choir_log(
                            gsheet,
                            DATABASE_SPREADSHEET_ID,  # ✅ Pakai dari settings
                            rec.choir_name,
                            rec.coordinator_name,
                            rec.wa_number,
                            preview=reminder_text[:100],
                            hash_value=hash_value,
                            status=f"error: {e}"
                        )
        await asyncio.sleep(random.uniform(6, 15))

    print("\n✅ All choir reminders processed!", flush=True)



async def check_and_run():
    # await send_organist_notification_reminders()
    # await send_choir_notification_reminders()
    # return 
    whatsAppBot = WhatsAppBot()
    admin_chat_id = "1731149425"
    
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