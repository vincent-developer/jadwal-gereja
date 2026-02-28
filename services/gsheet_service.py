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
        self._spreadsheet_cache: dict = {}  # keyed by spreadsheet_id
        self._worksheet_cache: dict = {}    # keyed by (spreadsheet_id, worksheet_name)
    
    def get_spreadsheet(self, spreadsheet_id: str):
        """Get spreadsheet by ID (cached per session)"""
        if spreadsheet_id not in self._spreadsheet_cache:
            self._spreadsheet_cache[spreadsheet_id] = self.client.open_by_key(spreadsheet_id)
        return self._spreadsheet_cache[spreadsheet_id]
    
    def get_worksheet(self, spreadsheet_id: str, worksheet_name: str):
        """Get worksheet by name (cached per session)"""
        key = (spreadsheet_id, worksheet_name)
        if key not in self._worksheet_cache:
            spreadsheet = self.get_spreadsheet(spreadsheet_id)
            self._worksheet_cache[key] = spreadsheet.worksheet(worksheet_name)
        return self._worksheet_cache[key]
    
    def read_all_values(self, spreadsheet_id: str, worksheet_name: str) -> list:
        """Read all values from a worksheet"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        return sheet.get_all_values()
    
    def read_all_records(self, spreadsheet_id: str, worksheet_name: str) -> list:
        """Read all records as list of dicts"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        return sheet.get_all_records()
    
    def get_or_create_worksheet(self, spreadsheet_id: str, worksheet_name: str, rows: int = 10, cols: int = 7):
        """Get worksheet or create if not exists (result cached per session)"""
        key = (spreadsheet_id, worksheet_name)
        if key in self._worksheet_cache:
            return self._worksheet_cache[key]
        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        try:
            sheet = spreadsheet.worksheet(worksheet_name)
        except WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=str(rows),
                cols=str(cols)
            )
        self._worksheet_cache[key] = sheet
        return sheet
    
    def append_row(self, spreadsheet_id: str, worksheet_name: str, values: list):
        """Append a row to worksheet"""
        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)
        sheet.append_row(values)

    def flush_log_writes(self, spreadsheet_id: str, worksheet_name: str, pending_writes: list) -> None:
        """
        Flush all deferred log writes in a single batch operation.
        pending_writes is a list of dicts:
          {"type": "update", "row": <int>, "values": <list>}
          {"type": "append", "values": <list>}
        All updates are batched into one batch_update call.
        All appends are batched into one append_rows call.
        """
        if not pending_writes:
            return

        sheet = self.get_worksheet(spreadsheet_id, worksheet_name)

        update_requests = []
        append_rows_data = []

        for entry in pending_writes:
            if entry["type"] == "update":
                num_cols = len(entry["values"])
                end_col = chr(64 + num_cols)
                update_requests.append({
                    "range": f"A{entry['row']}:{end_col}{entry['row']}",
                    "values": [entry["values"]]
                })
            elif entry["type"] == "append":
                append_rows_data.append(entry["values"])

        if update_requests:
            sheet.batch_update(update_requests)

        if append_rows_data:
            sheet.append_rows(append_rows_data)

        print(f"✅ Flushed {len(pending_writes)} log write(s) to '{worksheet_name}'", flush=True)
    
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