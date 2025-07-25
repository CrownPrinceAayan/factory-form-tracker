import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scope for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

# Load credentials from environment variable
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

# Build the Drive API service
drive_service = build('drive', 'v3', credentials=credentials)

def upload_to_drive(file_path, filename, folder_id=None):
    try:
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

        logger.info(f"✅ Uploaded to Drive. File ID: {file.get('id')}")
        return file.get('id')

    except Exception as e:
        logger.error(f"❌ Failed to upload to Google Drive: {e}")
        return None
