# drive_uploader.py
import os
import pickle
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

def get_drive_service():
    creds = None
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/drive.file"])
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name, folder_id=None):
    service = get_drive_service()
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    media = MediaFileUpload(file_path, mimetype='application/pdf')
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    print("✅ Uploaded:", uploaded_file.get('webViewLink'))
    return uploaded_file.get('webViewLink')
