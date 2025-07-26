import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drive_uploader")

# Scopes required for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

# Initialize Google Drive service
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    logger.info("✅ Google Drive service initialized.")
except Exception as e:
    logger.exception("❌ Google Drive init failed")
    drive_service = None

def upload_to_drive(file_path, filename, folder_id=None):
    """
    Uploads a file to Google Drive.
    
    Args:
        file_path (str): Path to the local file.
        filename (str): Name to use in Drive.
        folder_id (str, optional): Drive folder ID to upload into.
    
    Returns:
        str | None: File ID if successful, else None.
    """
    if not drive_service:
        logger.error("❌ Google Drive service not initialized.")
        return None

    try:
        logger.info(f"📤 Uploading {filename} to Google Drive…")
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype='application/pdf')

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = uploaded_file.get('id')
        logger.info(f"✅ Uploaded. File ID: {file_id}")
        return file_id

    except Exception as e:
        logger.exception("❌ Upload to Google Drive failed")
        return None
