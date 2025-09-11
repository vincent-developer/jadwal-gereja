# %%
import gspread
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from helpers.connection import get_google_credentials



def get_first_advent(year):
    """Cari Minggu Adven pertama (Minggu sebelum 25 Desember, hari Minggu terakhir sebelum Natal)"""
    dec_25 = datetime(year, 12, 25)
    # Mundur ke Minggu
    days_to_sunday = dec_25.weekday() + 1  # Monday=0..Sunday=6
    first_advent = dec_25 - timedelta(days=days_to_sunday + 21)  # 4 minggu sebelum Natal
    return first_advent

def liturgical_year(date):
    """Tentukan Tahun Liturgi A/B/C berdasarkan tanggal."""
    year = date.year
    first_advent = get_first_advent(year)

    if date >= first_advent:
        lit_year = year + 1  # masuk ke tahun liturgi berikutnya
    else:
        lit_year = year

    # Tahun 2020 = A → jadi lit_year % 3 mappingnya:
    # 2020 % 3 = 1 → A
    # 2021 % 3 = 2 → B
    # 2022 % 3 = 0 → C
    mapping = {1: "A", 2: "B", 0: "C"}
    return mapping[lit_year % 3]

# ====================================
# 1. Setup koneksi Google Sheets
# ====================================
SPREADSHEET_ID = "1xMNjbpQJhh8jTOaNlxPWy9B2nTEMBAURR9Ys3O90jlM"  # GANTI SESUAI ID
WORKSHEET_NAME = "Jadwal Pasdior"  # ganti sesuai worksheet

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = get_google_credentials(scope)
client = gspread.authorize(creds)

# ====================================
# 2. Ambil semua data lalu potong mulai B5
# ====================================
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
all_data = sheet.get_all_values()  # semua baris dan kolom yang ada isinya

# Potong: mulai baris ke-5 (index 4) dan kolom B–K (index 1 sampai 10)
data = [row[1:11] for row in all_data[4:] if len(row) >= 11]
df = pd.DataFrame(data, columns=["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]).copy()

# ====================================
# 3. Update kolom F & G berdasarkan J & K
# ====================================
mask_j = df["J"].astype(str).str.strip() != ""
df.loc[mask_j, "F"] = df.loc[mask_j, "J"]

mask_k = df["K"].astype(str).str.strip() != ""
df.loc[mask_k, "G"] = df.loc[mask_k, "K"]

# ====================================
# 4. Data tambahan (O–R)
# ====================================
data_extra = [row[14:18] for row in all_data[4:] if len(row) >= 18]
df_extra = pd.DataFrame(data_extra, columns=["O", "P", "Q", "R"]).copy()

# Sesuaikan ke format utama
df_extra["B"] = df_extra["O"]
df_extra["C"] = df_extra["P"]
df_extra["F"] = df_extra["Q"]
df_extra["G"] = df_extra["R"]
df_extra["D"] = ""
df_extra["E"] = ""
df_extra = df_extra[["B", "C", "D", "E", "F", "G"]].copy()

# Gabungkan
df_all = pd.concat([df[["B", "C", "D", "E", "F", "G"]], df_extra], ignore_index=True)

# ====================================
# 5. Filter kolom G == "Vincent" & tanggal >= hari ini
# ====================================
df_vincent = df_all[df_all["G"] == "Vincent"].copy()

month_map = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Sept": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

# Bersihkan & parse tanggal
b_str = (
    df_vincent["B"]
    .astype(str)
    .str.strip()
)
b_str_num = b_str.replace(month_map, regex=True)
b_dt = pd.to_datetime(b_str_num, dayfirst=True, errors="coerce")

# Fallback jika serial number Excel
serial_mask = b_str.str.match(r"^\d{4,6}$", na=False)
b_dt.loc[serial_mask] = (
    pd.to_datetime("1899-12-30") +
    pd.to_timedelta(b_str.loc[serial_mask].astype(int), unit="D")
)

df_vincent.loc[:, "B_dt"] = b_dt

# Filter tanggal >= hari ini
today_jkt = datetime.now(ZoneInfo("Asia/Jakarta")).date()
df_vincent = df_vincent[df_vincent["B_dt"].dt.date >= today_jkt].copy()

# Sorting by tanggal
df_vincent = df_vincent.sort_values(by="B_dt").reset_index(drop=True)

# ====================================
# 6. Format Output
# ====================================
df_clean = df_vincent[["B", "C", "D", "E", "F", "G", "B_dt"]].copy()

df_clean.columns = ["Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis", "tgl-format"]


# Tambahkan tahun liturgi (A/B/C)
df_clean["Tahun Liturgi"] = df_clean["tgl-format"].apply(
    lambda x: liturgical_year(x)
)

# Nama hari (Indonesia)
import locale
try:
    locale.setlocale(locale.LC_TIME, "id_ID.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "id_ID")
    except:
        pass

df_clean["Hari"] = df_clean["tgl-format"].dt.strftime("%A")

# Reorder kolom
df_clean = df_clean[["Hari", "Tanggal", "Jam", "Anamnesis", "Cara Tobat", "Koor", "Organis", "Tahun Liturgi"]]

# Tambahkan kolom Weekday (yes/no)
df_clean["Weekday"] = df_clean["Hari"].apply(lambda x: "yes" if x not in ["Sabtu", "Minggu", "Saturday", "Sunday"] else "no")

# ====================================
# 7. Output
# ====================================
# print("📊 Data terformat:")
# display(df_clean)
# currently comment because not supported by pure python

# ====================================
# 8. Simpan hasil ke Google Sheet lain
# ====================================
SPREADSHEET_ID_OUTPUT = "1nqY5jNzJvsy7v37jnb-rlSDUNvsLYiuHq5-ryAW1Kxs"  # Ganti ID sheet tujuan
WORKSHEET_OUTPUT = "jadwal"  # Ganti nama sheet tujuan

# Pastikan worksheet tujuan ada, kalau tidak buat baru
try:
    sheet_out = client.open_by_key(SPREADSHEET_ID_OUTPUT).worksheet(WORKSHEET_OUTPUT)
except gspread.exceptions.WorksheetNotFound:
    sheet_out = client.open_by_key(SPREADSHEET_ID_OUTPUT).add_worksheet(
        title=WORKSHEET_OUTPUT,
        rows=str(len(df_clean) + 10),
        cols=str(len(df_clean.columns) + 5)
    )

# Hapus isi lama, lalu tulis data baru
sheet_out.clear()
sheet_out.update(
    [df_clean.columns.tolist()] + df_clean.astype(str).values.tolist()
)

# Tambahkan Last Update di satu cell (misalnya di J1, supaya tidak ganggu tabel)
from datetime import datetime
from pytz import timezone

tz = timezone("Asia/Jakarta")
last_update_str = f"Last Update: {datetime.now(tz).strftime('%d-%b-%Y %H:%M:%S WIB')}"
sheet_out.update_acell('K1', last_update_str)

# Ambil bulan & tahun sekarang
today = datetime.today()
bulan = today.month
tahun = today.year

# Generate URL
url = f"https://www.imankatolik.or.id/kalender.php?b={bulan}&t={tahun}"

sheet_out.update_acell('K2', "Kalender Liturgi:")
sheet_out.update_acell('L2', url)

print(f"✅ Data berhasil disimpan ke Google Sheet ID: {SPREADSHEET_ID_OUTPUT}, Sheet: {WORKSHEET_OUTPUT}")




# %%



