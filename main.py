import os
from flask import Flask, request, jsonify
from google.auth import default
from googleapiclient.discovery import build
import googleapiclient.http
from functools import wraps

app = Flask(__name__)

# 🔒 Hardcoded workspace folder ID
WORKSPACE_FOLDER_ID = "1kbgDJtcbuwPM5pL_2m_0m5KpuiCNpQMh"  # Replace with your actual folder ID

# 🔑 API Key from environment
API_KEY = os.environ.get("GPT_API_KEY")

# 🧱 Middleware decorator for API key protection
def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": {"type": "auth", "message": "Missing or invalid Authorization header"}}), 401
        token = auth.split(" ", 1)[1].strip()
        if token != API_KEY:
            return jsonify({"error": {"type": "auth", "message": "Invalid API key"}}), 403
        return fn(*args, **kwargs)
    return wrapper

# 📡 Google Drive service instance
def get_drive_service():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

# 📂 Read a file from the workspace folder
@app.route("/drive/read", methods=["POST"])
@require_api_key
def read_file():
    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": {"type": "validation", "message": "Missing 'filename'"}}), 400

    try:
        drive = get_drive_service()

        results = drive.files().list(
            q=f"name = '{filename}' and trashed = false and '{WORKSPACE_FOLDER_ID}' in parents",
            fields="files(id, name, mimeType)",
            pageSize=1
        ).execute()

        files = results.get("files", [])
        if not files:
            return jsonify({"error": {"type": "not_found", "message": f"File '{filename}' not found in workspace"}}), 404

        file_id = files[0]["id"]
        mime_type = files[0]["mimeType"]

        if mime_type.startswith("application/vnd.google-apps"):
            export_mime = {
                "application/vnd.google-apps.document": "text/plain",
                "application/vnd.google-apps.spreadsheet": "text/csv",
                "application/vnd.google-apps.presentation": "text/plain"
            }.get(mime_type, "text/plain")
            content = drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        else:
            content = drive.files().get_media(fileId=file_id).execute()

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return jsonify({"error": {"type": "unsupported_format", "message": "File is not a UTF-8 text file"}}), 415

        return jsonify({
            "filename": filename,
            "content": text
        })

    except Exception as e:
        return jsonify({"error": {"type": "exception", "message": str(e)}}), 500

# 💾 Create or update a file in the workspace folder
@app.route("/drive/write", methods=["POST"])
@require_api_key
def write_file():
    data = request.get_json()
    filename = data.get("filename")
    content = data.get("content")

    if not filename or content is None:
        return jsonify({"error": {"type": "validation", "message": "Missing 'filename' or 'content'"}}), 400

    try:
        drive = get_drive_service()

        results = drive.files().list(
            q=f"name = '{filename}' and trashed = false and '{WORKSPACE_FOLDER_ID}' in parents",
            fields="files(id)",
            pageSize=1
        ).execute()

        files = results.get("files", [])
        media_body = googleapiclient.http.MediaInMemoryUpload(
            content.encode("utf-8"),
            mimetype=detect_mime_type(filename)
        )

        if files:
            file_id = files[0]["id"]
            drive.files().update(fileId=file_id, media_body=media_body).execute()
            return jsonify({"status": "updated", "file_id": file_id})
        else:
            file_metadata = {
                "name": filename,
                "parents": [WORKSPACE_FOLDER_ID]
            }
            file = drive.files().create(
                body=file_metadata,
                media_body=media_body,
                fields="id"
            ).execute()
            return jsonify({"status": "created", "file_id": file["id"]})

    except Exception as e:
        return jsonify({"error": {"type": "exception", "message": str(e)}}), 500

# 📄 List all files in the workspace folder
@app.route("/drive/list", methods=["GET"])
@require_api_key
def list_files():
    try:
        drive = get_drive_service()

        results = drive.files().list(
            q=f"'{WORKSPACE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, modifiedTime, size, mimeType)",
            orderBy="modifiedTime desc",
            pageSize=50
        ).execute()

        files = results.get("files", [])
        return jsonify({
            "count": len(files),
            "files": files
        })

    except Exception as e:
        return jsonify({"error": {"type": "exception", "message": str(e)}}), 500

# ✅ Basic check route
@app.route("/")
def hello():
    return "✅ Hello from drive-api-hello via GitHub & Cloud Run!"

# 🔍 Guess MIME type from filename
def detect_mime_type(filename):
    if filename.endswith(".md"):
        return "text/markdown"
    elif filename.endswith(".json"):
        return "application/json"
    elif filename.endswith(".csv"):
        return "text/csv"
    else:
        return "text/plain"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
