import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    logger.info("✅ Google Drive service initialized.")
except Exception as e:
    logger.error(f"❌ Google Drive init failed: {e}")

def upload_to_drive(file_path, filename, folder_id=None):
    try:
        logger.info(f"📤 Uploading {filename} to Google Drive…")
        file_metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }
        media = MediaFileUpload(file_path, mimetype='application/pdf')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logger.info(f"✅ Uploaded. File ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        return None
