import sys
from babel.dates import format_date
import gspread
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pytz import timezone
from gspread.exceptions import WorksheetNotFound
from dotenv import load_dotenv, find_dotenv
import locale
import nest_asyncio

# =======================================
# ENVIRONMENT SETUP & IMPORTS
# =======================================
sys.path.append("..")
from utils.telegram_bot import TelegramBot
from helpers.connection import get_google_credentials

load_dotenv(find_dotenv())
nest_asyncio.apply()

# =======================================
# 1. HELPER FUNCTIONS
# =======================================

def get_first_advent(year):
    """Return the date of the first Advent Sunday for the given year."""
    dec_25 = datetime(year, 12, 25)
    days_to_sunday = dec_25.weekday() + 1
    return dec_25 - timedelta(days=days_to_sunday + 21)

def liturgical_year(date):
    """Determine the liturgical year (A, B, or C) based on Advent."""
    year = date.year
    first_advent = get_first_advent(year)
    lit_year = year + 1 if date >= first_advent else year
    mapping = {1: "A", 2: "B", 0: "C"}
    return mapping[lit_year % 3]

def read_last_log(client, spreadsheet_id, chat_id):
    """Return last log entry for this chat_id, or None if not found."""
    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet("Telegram Chat Log")
        records = sheet.get_all_records()

        for row in records:
            if str(row.get("Chat ID")).strip() == str(chat_id).strip():
                return row

        return None

    except WorksheetNotFound:
        # Create sheet if missing
        sheet = client.open_by_key(spreadsheet_id).add_worksheet(
            title="Telegram Chat Log", rows="10", cols="6"
        )
        sheet.append_row(["Timestamp", "Name", "Chat ID", "Message Preview", "Schedule Hash", "Status"])
        return None
    
def update_log(client, spreadsheet_id, name, chat_id, preview, hash_value, status):
    """Update or insert log row ensuring only one record exists per chat_id."""
    sheet = client.open_by_key(spreadsheet_id).worksheet("Telegram Chat Log")
    records = sheet.get_all_records()

    timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")

    # Search existing row
    for idx, row in enumerate(records, start=2):  # row 1 = header
        if str(row.get("Chat ID")).strip() == str(chat_id).strip():
            sheet.update(range_name=f"A{idx}:F{idx}", values=[[timestamp, name, chat_id, preview, hash_value, status]])
            return

    # If not found → append new row
    sheet.append_row([timestamp, name, chat_id, preview, hash_value, status])


def save_df_to_gsheet(spreadsheet, worksheet_output_name, df):
    """Save a DataFrame to a specific Google Sheets worksheet."""
    try:
        sheet_out = spreadsheet.worksheet(worksheet_output_name)
    except WorksheetNotFound:
        sheet_out = spreadsheet.add_worksheet(
            title=worksheet_output_name,
            rows=str(len(df) + 10),
            cols=str(len(df.columns) + 5)
        )

    sheet_out.clear()
    data = [df.columns.tolist()] + df.astype(str).values.tolist()

    tz = timezone("Asia/Jakarta")
    last_update_str = f"Last Update: {datetime.now(tz).strftime('%d-%b-%Y %H:%M:%S WIB')}"
    today = datetime.today()
    url = f"https://www.imankatolik.or.id/kalender.php?b={today.month}&t={today.year}"

    requests = [
        {"range": f"A1:{chr(65+len(df.columns)-1)}{len(df)+1}", "values": data},
        {"range": "K1", "values": [[last_update_str]]},
        {"range": "K2", "values": [["Liturgical Calendar:"]]},
        {"range": "L2", "values": [[url]]}
    ]
    sheet_out.batch_update(requests)
    print(f"✅ Saved to Google Sheet: {worksheet_output_name}", flush=True)

# =======================================
# 2. GOOGLE SHEETS CONNECTION
# =======================================
SPREADSHEET_ID = "1xMNjbpQJhh8jTOaNlxPWy9B2nTEMBAURR9Ys3O90jlM"
WORKSHEET_NAME = "Jadwal Pasdior"
SPREADSHEET_ID_OUTPUT = "1nqY5jNzJvsy7v37jnb-rlSDUNvsLYiuHq5-ryAW1Kxs"
WORKSHEET_OUTPUT = "jadwal"
ORGANIST_WORKSHEET_NAME = "Data Organis"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = get_google_credentials(scope)
client = gspread.authorize(creds)

# =======================================
# 3. LOAD ORGANIST LIST
# =======================================
organist_sheet = client.open_by_key(SPREADSHEET_ID_OUTPUT).worksheet(ORGANIST_WORKSHEET_NAME)
all_organist_data = organist_sheet.get_all_values()

organist_records = []
for row in all_organist_data[1:]:
    if not row or not row[0].strip():
        continue
    name = row[0].strip()
    chat_id = row[1].strip() if len(row) > 1 and row[1].strip() else None
    organist_records.append({"name": name, "chat_id": chat_id})

clean_organist_list_name = [r["name"].lower() for r in organist_records]

# =======================================
# 4. LOAD & PREPROCESS DATA
# =======================================
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
all_data = sheet.get_all_values()

# Extract main data columns
data = [row[1:11] for row in all_data[4:] if len(row) >= 11]
df = pd.DataFrame(data, columns=["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]).copy()

# Override columns F,G if J,K are filled
mask_j = df["J"].astype(str).str.strip() != ""
df.loc[mask_j, ["F", "G"]] = df.loc[mask_j, ["J", "K"]].values

# disabled because new structure apply on main
# # Extract extra data (second schedule section)
# data_extra = [row[14:18] for row in all_data[4:] if len(row) >= 18]
# df_extra = pd.DataFrame(data_extra, columns=["O", "P", "Q", "R"])
# df_extra["B"], df_extra["C"], df_extra["F"], df_extra["G"] = df_extra["O"], df_extra["P"], df_extra["Q"], df_extra["R"]
# df_extra["D"], df_extra["E"] = "", ""
# df_extra = df_extra[["B", "C", "D", "E", "F", "G"]]

# # Merge both sections
# df_all = pd.concat([df[["B", "C", "D", "E", "F", "G"]], df_extra], ignore_index=True)
df_all = df[["B", "C", "D", "E", "F", "G"]]

# Convert dates
month_map = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Sept": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}
b_str = df_all["B"].astype(str).str.strip().replace(month_map, regex=True)
b_dt = pd.to_datetime(b_str, dayfirst=True, errors="coerce")

# Handle Excel serial date format
serial_mask = b_str.str.match(r"^\d{4,6}$", na=False)
b_dt.loc[serial_mask] = pd.to_datetime("1899-12-30") + pd.to_timedelta(b_str.loc[serial_mask].astype(int), unit="D")

df_all["B_dt"] = b_dt
today_jkt = datetime.now(ZoneInfo("Asia/Jakarta")).date()
df_all = df_all[df_all["B_dt"].dt.date >= today_jkt].copy().sort_values("B_dt").reset_index(drop=True)

# Clean and standardize columns
df_clean = df_all[["B", "C", "D", "E", "F", "G", "B_dt"]].copy()
df_clean.columns = ["Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis", "tgl-format"]
df_clean["Tahun Liturgi"] = df_clean["tgl-format"].apply(liturgical_year)

# Set Indonesian locale
try:
    locale.setlocale(locale.LC_TIME, "id_ID.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "id_ID")
    except:
        pass

# Format day name (Indonesian)
df_clean["Hari"] = df_clean["tgl-format"].apply(
    lambda d: format_date(d, "EEEE", locale="id") if pd.notnull(d) else ""
)
df_clean["Weekday"] = df_clean["Hari"].apply(lambda x: "yes" if x not in ["Sabtu", "Minggu", "Saturday", "Sunday"] else "no")

# =======================================
# 5. TELEGRAM REMINDER SENDER
# =======================================
spreadsheet = client.open_by_key(SPREADSHEET_ID_OUTPUT)


async def send_telegram_reminders():
    print("🚀 Starting reminder process...\n", flush=True)

    today = datetime.now(ZoneInfo("Asia/Jakarta"))
    is_tuesday = today.strftime("%A").lower() == "tuesday"

    if is_tuesday:
        print("📅 Today is Tuesday — will send Telegram reminders.\n", flush=True)
    else:
        print(f"📅 Today is {today.strftime('%A')} — will only update Google Sheets (no Telegram send).\n", flush=True)

    for rec in organist_records:
        name, chat_id = rec["name"], rec["chat_id"]
        print(f"🔹 Processing {name}...", flush=True)

        # Filter schedule
        filter_df = df_clean[df_clean["Organis"].str.lower() == name.lower()].copy()

        # Drop the 'tgl-format' column before saving
        df_to_save = filter_df.drop(columns=['tgl-format'])
        
        
        # reorder the table
        new_order = ["Hari", "Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis","Tahun Liturgi", "Weekday"]
        df_to_save = df_to_save[new_order]
        
        await asyncio.to_thread(save_df_to_gsheet, spreadsheet, f"Jadwal {name.capitalize()}", df_to_save)
        


        # Always update Sheet, but send Telegram only on Tuesday
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

            reminder_text = (
                f"Hi {name.capitalize()}, jadwal organis berikutnya adalah:\n" +
                "\n".join(tanggal_list) +
                "\n\nUntuk jadwal yang lebih update silahkan cek di link berikut:\nhttps://linktr.ee/pasdiormabes"
            )


            print(reminder_text, flush=True)
            print("=" * 60, flush=True)


            if chat_id:
                # Buat schedule hash berdasarkan tanggal & jam jadwal
                hash_value = "|".join(tanggal_list)

                # Cek log terakhir untuk chat_id ini
                previous_log = read_last_log(client, SPREADSHEET_ID_OUTPUT, chat_id)

                if previous_log and previous_log.get("Schedule Hash") == hash_value:
                    # Jadwal sama → skip kirim
                    print(f"⏭ SKIPPED (duplicate schedule): {name}", flush=True)
                    update_log(client, SPREADSHEET_ID_OUTPUT, name, chat_id, reminder_text[:100], hash_value, "skipped")
                else:
                    try:
                        bot = TelegramBot(chat_id=chat_id)
                        await bot.send(reminder_text)
                        print(f"📨 Reminder sent to {name} ({chat_id})", flush=True)
                        update_log(client, SPREADSHEET_ID_OUTPUT, name, chat_id, reminder_text[:100], hash_value, "sent")
                    except Exception as e:
                        print(f"⚠️ Failed to send Telegram to {name}: {e}", flush=True)
                        update_log(client, SPREADSHEET_ID_OUTPUT, name, chat_id, reminder_text[:100], hash_value, f"error: {e}")



        await asyncio.sleep(2)

    print("\n✅ All reminders processed!", flush=True)


# =======================================
# 6. RUN MAIN FUNCTION
# =======================================
if __name__ == "__main__":
    asyncio.run(send_telegram_reminders())

