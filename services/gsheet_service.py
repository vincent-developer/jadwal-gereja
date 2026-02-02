"""
Google Sheets service for reading and writing data
"""

import gspread
from gspread.exceptions import WorksheetNotFound
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from config.settings import get_google_credentials
from config.constants import JAKARTA_TZ


class GoogleSheetsService:
    """Handle all Google Sheets operations"""
    
    def __init__(self):
        """Initialize Google Sheets client"""
        creds = get_google_credentials()
        self.client = gspread.authorize(creds)
    
    def get_spreadsheet(self, spreadsheet_id: str):
        """Get spreadsheet by ID"""
        return self.client.open_by_key(spreadsheet_id)
    
    def get_worksheet(self, spreadsheet_id: str, worksheet_name: str):
        """Get worksheet by name"""
        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        return spreadsheet.worksheet(worksheet_name)
    
    def read_all_values(self, spreadsheet_id: str, worksheet_name: str) -> list:
        """Read all values from a worksheet"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        return sheet.get_all_values()
    
    def read_all_records(self, spreadsheet_id: str, worksheet_name: str) -> list:
        """Read all records as list of dicts"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        return sheet.get_all_records()
    
    def get_or_create_worksheet(self, spreadsheet_id: str, worksheet_name: str, rows: int = 10, cols: int = 7):
        """Get worksheet or create if not exists"""
        try:
            spreadsheet = self.get_spreadsheet(spreadsheet_id)
            sheet = spreadsheet.worksheet(worksheet_name)
            return sheet
        except WorksheetNotFound:
            spreadsheet = self.get_spreadsheet(spreadsheet_id)
            sheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=str(rows),
                cols=str(cols)
            )
            return sheet
    
    def append_row(self, spreadsheet_id: str, worksheet_name: str, values: list):
        """Append a row to worksheet"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        sheet.append_row(values)
    
    def update_row(self, spreadsheet_id: str, worksheet_name: str, row_index: int, values: list):
        """Update specific row"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        num_cols = len(values)
        end_col = chr(64 + num_cols)  # A=65, so 64+7=G for 7 columns
        sheet.update(
            range_name=f"A{row_index}:{end_col}{row_index}",
            values=[values]
        )
    
    def clear_worksheet(self, spreadsheet_id: str, worksheet_name: str):
        """Clear all data in worksheet"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        sheet.clear()
    
    def save_dataframe(
        self, 
        spreadsheet_id: str, 
        worksheet_name: str, 
        df: pd.DataFrame,
        add_metadata: bool = True
    ):
        """
        Save DataFrame to Google Sheet with optional metadata
        
        Args:
            spreadsheet_id: Google Sheets ID
            worksheet_name: Name of the worksheet
            df: DataFrame to save
            add_metadata: Whether to add last update timestamp and calendar link
        """
        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        
        # Get or create worksheet
        try:
            sheet = spreadsheet.worksheet(worksheet_name)
        except WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=str(len(df) + 10),
                cols=str(len(df.columns) + 5),
            )
        
        # Clear and prepare data
        sheet.clear()
        data = [df.columns.tolist()] + df.astype(str).values.tolist()
        
        # Prepare batch update requests
        requests = [
            {
                "range": f"A1:{chr(65 + len(df.columns) - 1)}{len(df) + 1}",
                "values": data
            }
        ]
        
        # Add metadata if requested
        if add_metadata:
            tz = ZoneInfo(JAKARTA_TZ)
            last_update_str = (
                f"Last Update: {datetime.now(tz).strftime('%d-%b-%Y %H:%M:%S WIB')}"
            )
            today = datetime.today()
            calendar_url = f"https://www.imankatolik.or.id/kalender.php?b={today.month}&t={today.year}"
            
            requests.extend([
                {"range": "K1", "values": [[last_update_str]]},
                {"range": "K2", "values": [["Liturgical Calendar:"]]},
                {"range": "L2", "values": [[calendar_url]]},
            ])
        
        # Execute batch update
        sheet.batch_update(requests)
        print(f"✅ Saved to Google Sheet: {worksheet_name}", flush=True)