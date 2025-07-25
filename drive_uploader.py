# drive_uploader.py

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None
    TOKEN_PATH = 'drive_token.pickle'
    CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'credentials.json')

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)


def upload_to_drive(file_path, file_name, folder_id=None):
    service = get_drive_service()

    # Add 'parents' if a folder_id is provided
    file_metadata = {
        'name': file_name,
        'parents': [folder_id] if folder_id else []
    }

    media = MediaFileUpload(file_path, mimetype='application/pdf')
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    print("✅ Uploaded:", uploaded_file.get('webViewLink'))
    return uploaded_file.get('webViewLink')



# ✅ ADD THIS SECTION TO TEST
if __name__ == '__main__':
    test_file = 'sample.pdf'  # Replace with a real PDF path on your PC
    if os.path.exists(test_file):
        upload_to_drive(test_file, 'Test Upload.pdf')
    else:
        print("❌ sample.pdf not found. Put any PDF in your folder and rename it to 'sample.pdf'")