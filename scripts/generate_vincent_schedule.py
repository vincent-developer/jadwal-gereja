import gspread
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from helpers.connection import get_google_credentials
from gspread.exceptions import WorksheetNotFound
from pytz import timezone
import locale


# ==============================
# 1. Helper Functions
# ==============================
def get_first_advent(year):
    """Find the first Advent Sunday (last Sunday before Christmas)."""
    dec_25 = datetime(year, 12, 25)
    # Go backward to Sunday
    days_to_sunday = dec_25.weekday() + 1  # Monday=0..Sunday=6
    first_advent = dec_25 - timedelta(days=days_to_sunday + 21)  # 4 Sundays before Christmas
    return first_advent


def liturgical_year(date):
    """Determine the Liturgical Year (A/B/C) based on a given date."""
    year = date.year
    first_advent = get_first_advent(year)

    if date >= first_advent:
        lit_year = year + 1  # move to next liturgical year
    else:
        lit_year = year

    # Mapping cycle: 2020 = A → lit_year % 3
    # 2020 % 3 = 1 → A
    # 2021 % 3 = 2 → B
    # 2022 % 3 = 0 → C
    mapping = {1: "A", 2: "B", 0: "C"}
    return mapping[lit_year % 3]


def save_df_to_gsheet(spreadsheet, worksheet_output_name, df):
    """
    Save DataFrame to a Google Sheets worksheet.

    Params:
        spreadsheet (gspread.Spreadsheet): target spreadsheet object
        worksheet_output_name (str): worksheet/tab name
        df (pandas.DataFrame): data to be written
    """
    # 1. Get worksheet or create a new one if not exists
    try:
        sheet_out = spreadsheet.worksheet(worksheet_output_name)
    except WorksheetNotFound:
        sheet_out = spreadsheet.add_worksheet(
            title=worksheet_output_name,
            rows=str(len(df) + 10),
            cols=str(len(df.columns) + 5)
        )

    # 2. Clear old content
    sheet_out.clear()

    # 3. Prepare data (header + DataFrame content)
    data = [df.columns.tolist()] + df.astype(str).values.tolist()

    # 4. Additional metadata
    tz = timezone("Asia/Jakarta")
    last_update_str = f"Last Update: {datetime.now(tz).strftime('%d-%b-%Y %H:%M:%S WIB')}"

    today = datetime.today()
    bulan, tahun = today.month, today.year
    url = f"https://www.imankatolik.or.id/kalender.php?b={bulan}&t={tahun}"

    # 5. Combine all updates into batch_update (single API call)
    requests = [
        {
            "range": f"A1:{chr(65+len(df.columns)-1)}{len(df)+1}",
            "values": data
        },
        {"range": "K1", "values": [[last_update_str]]},
        {"range": "K2", "values": [["Liturgical Calendar:"]]},
        {"range": "L2", "values": [[url]]}
    ]

    sheet_out.batch_update(requests)

    print(f"✅ Data successfully saved to sheet: {worksheet_output_name}")


# ==============================
# 2. Google Sheets Connection
# ==============================
SPREADSHEET_ID = "1xMNjbpQJhh8jTOaNlxPWy9B2nTEMBAURR9Ys3O90jlM"  # Source Sheet ID
WORKSHEET_NAME = "Jadwal Pasdior"  # Source Worksheet
SPREADSHEET_ID_OUTPUT = "1nqY5jNzJvsy7v37jnb-rlSDUNvsLYiuHq5-ryAW1Kxs"  # Target Sheet ID
WORKSHEET_OUTPUT = "jadwal"  # Target Worksheet (default)
ORGANIST_WORKSHEET_NAME = "Data Organis"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = get_google_credentials(scope)
client = gspread.authorize(creds)


# ==============================
# 3. Load Organist List
# ==============================
organist_sheet = client.open_by_key(SPREADSHEET_ID_OUTPUT).worksheet(ORGANIST_WORKSHEET_NAME)
all_organist_data = organist_sheet.get_all_values()  # all rows and columns with values
names = [row[0] for row in all_organist_data[1:]]  # skip header
clean_organist_list_name = [name.lower() for name in names]


# ==============================
# 4. Load and Preprocess Data
# ==============================
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
all_data = sheet.get_all_values()  # all rows and columns with values

# Slice: start from row 5 (index 4) and columns B–K (index 1 to 10)
data = [row[1:11] for row in all_data[4:] if len(row) >= 11]
df = pd.DataFrame(data, columns=["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]).copy()

# Update F & G columns based on J & K
mask_j = df["J"].astype(str).str.strip() != ""
df.loc[mask_j, "F"] = df.loc[mask_j, "J"]
df.loc[mask_j, ["F", "G"]] = df.loc[mask_j, ["J", "K"]].values


# ==============================
# 5. Extra Data (O–R)
# ==============================
data_extra = [row[14:18] for row in all_data[4:] if len(row) >= 18]
df_extra = pd.DataFrame(data_extra, columns=["O", "P", "Q", "R"]).copy()

# Map to main format
df_extra["B"] = df_extra["O"]
df_extra["C"] = df_extra["P"]
df_extra["F"] = df_extra["Q"]
df_extra["G"] = df_extra["R"]
df_extra["D"] = ""
df_extra["E"] = ""
df_extra = df_extra[["B", "C", "D", "E", "F", "G"]].copy()

# Merge
df_all = pd.concat([df[["B", "C", "D", "E", "F", "G"]], df_extra], ignore_index=True)


# ==============================
# 6. Filter & Clean Dates
# ==============================
month_map = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Sept": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

# Clean and parse dates
b_str = df_all["B"].astype(str).str.strip()
b_str_num = b_str.replace(month_map, regex=True)
b_dt = pd.to_datetime(b_str_num, dayfirst=True, errors="coerce")

# Fallback: Excel serial numbers
serial_mask = b_str.str.match(r"^\d{4,6}$", na=False)
b_dt.loc[serial_mask] = (
    pd.to_datetime("1899-12-30") +
    pd.to_timedelta(b_str.loc[serial_mask].astype(int), unit="D")
)

df_all.loc[:, "B_dt"] = b_dt

# Filter for today or later
today_jkt = datetime.now(ZoneInfo("Asia/Jakarta")).date()
df_all = df_all[df_all["B_dt"].dt.date >= today_jkt].copy()

# Sort by date
df_all = df_all.sort_values(by="B_dt").reset_index(drop=True)


# ==============================
# 7. Final Output Format
# ==============================
df_clean = df_all[["B", "C", "D", "E", "F", "G", "B_dt"]].copy()
df_clean.columns = ["Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis", "tgl-format"]

# Add liturgical year (A/B/C)
df_clean["Tahun Liturgi"] = df_clean["tgl-format"].apply(lambda x: liturgical_year(x))

# Day names in Indonesian
try:
    locale.setlocale(locale.LC_TIME, "id_ID.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "id_ID")
    except:
        pass

df_clean["Hari"] = df_clean["tgl-format"].dt.strftime("%A")

# Reorder columns
df_clean = df_clean[["Hari", "Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis", "Tahun Liturgi"]]

# Add Weekday flag (yes/no)
df_clean["Weekday"] = df_clean["Hari"].apply(
    lambda x: "yes" if x not in ["Sabtu", "Minggu", "Saturday", "Sunday"] else "no"
)


# ==============================
# 8. Save Results to Google Sheets
# ==============================
spreadsheet = client.open_by_key(SPREADSHEET_ID_OUTPUT)

for name in clean_organist_list_name:
    filter_df = df_clean[df_clean["Organis"].str.lower() == name].copy()
    save_df_to_gsheet(spreadsheet=spreadsheet, worksheet_output_name="Jadwal " + name.capitalize(), df=filter_df)

# ==============================
# 9. Final Log
# ==============================
print("🎉 All data successfully updated and saved to Google Sheets.")
