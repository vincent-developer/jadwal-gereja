import os
from dotenv import load_dotenv
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

load_dotenv()

def connect_gdrive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(os.getenv("GOOGLE_DRIVE_CRED"))
    if gauth.credentials is None:
        raise ValueError("❌ Credentials belum ada, buat dulu di Google API Console")
    drive = GoogleDrive(gauth)
    print("✅ Google Drive connected!")
    return drive
