import os
import json
from flask import Flask, request, redirect, jsonify

from google.cloud import secretmanager
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- Configuration ---
SECRET_NAME = "gemini-drive-token"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
PROJECT_ID = os.environ.get('GCP_PROJECT') 

# --- Flask App Initialization ---
app = Flask(__name__)

# --- DEBUGGING: PRINT ALL ENVIRONMENT VARIABLES ---
print("--- ENVIRONMENT VARIABLES ---")
import os
for key, value in os.environ.items():
    print(f"{key}: {value}")
print("-----------------------------")
# --- END DEBUGGING ---

# --- Helper Functions ---
def get_secret_manager_client():
# --- Helper Functions ---
def get_secret_manager_client():
    """Initializes the Secret Manager client."""
    return secretmanager.SecretManagerServiceClient()

def get_credentials_from_secret():
    """Retrieves credentials from Secret Manager."""
    client = get_secret_manager_client()
    # The project ID is needed to construct the full secret path.
    project_id = os.environ.get('GCP_PROJECT')
    if not project_id:
        # Fallback or error if project ID is not set in the environment
        raise ValueError("GCP_PROJECT environment variable not set.")
        
    secret_version_name = f"projects/{project_id}/secrets/{SECRET_NAME}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": secret_version_name})
        creds_json = response.payload.data.decode("UTF-8")
        creds_dict = json.loads(creds_json)
        return Credentials.from_authorized_user_info(creds_dict, SCOPES)
    except Exception:
        return None # Secret not found or other error

def save_credentials_to_secret(credentials):
    """Saves credentials to Secret Manager, disabling old versions."""
    client = get_secret_manager_client()
    project_id = os.environ.get('GCP_PROJECT')
    if not project_id:
        raise ValueError("GCP_PROJECT environment variable not set.")

    secret_path = f"projects/{project_id}/secrets/{SECRET_NAME}"
    payload = credentials.to_json().encode("UTF-8")
    
    # Disable all existing enabled versions to ensure only one is latest
    try:
        versions = client.list_secret_versions(request={"parent": secret_path, "filter": "state=ENABLED"})
        for version in versions:
            client.disable_secret_version(request={"name": version.name})
    except Exception:
        # This can fail if there are no versions yet, which is fine.
        pass

    # Add the new secret version
    client.add_secret_version(parent=secret_path, payload={"data": payload})


def get_oauth_flow():
    """Builds the OAuth 2.0 flow object."""
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.google.com/token",
                "redirect_uris": [os.environ.get("REDIRECT_URI")]
            }
        },
        scopes=SCOPES,
        redirect_uri=os.environ.get("REDIRECT_URI")
    )

# --- Main Application Logic ---
@app.route('/authorize')
def authorize():
    """Starts the authorization process."""
    flow = get_oauth_flow()
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Handles the redirect from Google's consent screen."""
    flow = get_oauth_flow()
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        save_credentials_to_secret(credentials)
        return "<h1>Authorization successful!</h1><p>You can close this tab and return to Gemini.</p>"
    except Exception as e:
        return f"<h1>Error during authorization:</h1><p>{e}</p>", 500

@app.route('/edit-markdown', methods=['POST'])
def edit_markdown_file():
    """The main endpoint that Gemini will call."""
    credentials = get_credentials_from_secret()
    if not credentials:
        return jsonify({"error": "User not authenticated. Please visit the /authorize endpoint first."}), 401

    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
        save_credentials_to_secret(credentials)

    try:
        service = build('drive', 'v3', credentials=credentials)
        data = request.get_json()
        file_name = data.get('fileName')
        content_to_add = data.get('content')

        if not file_name or content_to_add is None:
            return jsonify({"error": "Missing 'fileName' or 'content' in request body."}), 400

        query = f"name='{file_name}.md' and mimeType='text/markdown' and trashed=false"
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])

        if not files:
            # If file not found, create it
            file_metadata = {
                'name': f"{file_name}.md",
                'mimeType': 'text/markdown'
            }
            from io import BytesIO
            from googleapiclient.http import MediaIoBaseUpload
            fh = BytesIO(content_to_add.encode('utf-8'))
            media_body = MediaIoBaseUpload(fh, mimetype='text/markdown', resumable=True)
            created_file = service.files().create(
                body=file_metadata,
                media_body=media_body,
                fields='id, name'
            ).execute()
            return jsonify({"success": True, "message": f"File '{created_file['name']}' did not exist and was created."})

        file_id = files[0]['id']

        from io import BytesIO
        from googleapiclient.http import MediaIoBaseUpload

        fh = BytesIO(content_to_add.encode('utf-8'))
        media_body = MediaIoBaseUpload(fh, mimetype='text/markdown', resumable=True)

        updated_file = service.files().update(
            fileId=file_id,
            media_body=media_body
        ).execute()

        return jsonify({"success": True, "message": f"Successfully updated '{updated_file['name']}'."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
