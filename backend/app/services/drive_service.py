from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

SERVICE_ACCOUNT_FILE = "service_account.json"

FOLDER_ID = "1vdb1bEQXYN4K3BO-mQkglVbKq4bUHlNL"  # ← Replace with your actual Google Drive folder ID


creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

service = build(
    "drive",
    "v3",
    credentials=creds
)


def upload_pdf_to_drive(file_path, file_name):

    try:
        file_metadata = {
            "name": file_name,
            "parents": [FOLDER_ID]
        }

        media = MediaFileUpload(
            file_path,
            mimetype="application/pdf"
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        file_id = file.get("id")

        service.permissions().create(
            fileId=file_id,
            body={
                "type": "anyone",
                "role": "reader"
            }
        ).execute()

        link = f"https://drive.google.com/file/d/{file_id}/view"
        print(f"💾 Drive Service: ✓ PDF uploaded successfully")
        print(f"💾 Drive Service: Share link: {link}")
        return link
        
    except Exception as e:
        print(f"💾 Drive Service: ⚠ Upload failed: {type(e).__name__}: {str(e)}")
        print(f"💾 Drive Service: Continuing without Drive link (optional service)")
        return None
