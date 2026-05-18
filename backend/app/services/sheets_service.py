import gspread

from oauth2client.service_account import (
    ServiceAccountCredentials
)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "service_account.json",
    scope
)

client = gspread.authorize(creds)

sheet = client.open(
    "AI Leads Tracker"
).sheet1


def log_lead_to_sheet(data):

    sheet.append_row([
        data.get("name"),
        data.get("email"),
        data.get("company"),
        data.get("website"),
        data.get("status"),
        data.get("drive_link"),
        str(data.get("created_at"))
    ])
