import os
import googleapiclient.http
from flask import Flask, request, jsonify
from google.auth import default
from googleapiclient.discovery import build

app = Flask(__name__)

WORKSPACE_FOLDER_ID = "1kbgDJtcbuwPM5pL_2m_0m5KpuiCNpQMh"  # Replace with your actual folder ID


def get_drive_service():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)




@app.route("/drive/list", methods=["GET"])
def list_files():
    try:
        drive = get_drive_service()

        results = drive.files().list(
            q=f"'{WORKSPACE_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, modifiedTime, size)",
            orderBy="modifiedTime desc",
            pageSize=50
        ).execute()

        files = results.get("files", [])
        return jsonify({
            "count": len(files),
            "files": files
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/drive/read", methods=["POST"])
def read_file():
    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Missing 'filename'"}), 400

    try:
        drive = get_drive_service()

        # Search for file in specific folder only
        results = drive.files().list(
            q=f"name = '{filename}' and trashed = false and '{WORKSPACE_FOLDER_ID}' in parents",
            fields="files(id, name)",
            pageSize=1
        ).execute()

        files = results.get("files", [])
        if not files:
            return jsonify({"error": f"File '{filename}' not found in workspace"}), 404

        file_id = files[0]["id"]

        content = drive.files().get_media(fileId=file_id).execute()

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return jsonify({"error": "File is not a UTF-8 text file"}), 415

        return jsonify({
            "filename": filename,
            "content": text
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/drive/write", methods=["POST"])
def write_file():
    data = request.get_json()
    filename = data.get("filename")
    content = data.get("content")

    if not filename or content is None:
        return jsonify({"error": "Missing 'filename' or 'content'"}), 400

    try:
        drive = get_drive_service()

        # Check if file exists
        results = drive.files().list(
            q=f"name = '{filename}' and trashed = false and '{WORKSPACE_FOLDER_ID}' in parents",
            fields="files(id)",
            pageSize=1
        ).execute()

        files = results.get("files", [])
        media = {'mimeType': 'text/plain'}

        if files:
            # File exists → update
            file_id = files[0]["id"]
            media_body = googleapiclient.http.MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
            drive.files().update(fileId=file_id, media_body=media_body).execute()
            return jsonify({"status": "updated", "file_id": file_id})
        else:
            # File doesn't exist → create
            file_metadata = {
                "name": filename,
                "parents": [WORKSPACE_FOLDER_ID]
            }
            media_body = googleapiclient.http.MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
            file = drive.files().create(body=file_metadata, media_body=media_body, fields="id").execute()
            return jsonify({"status": "created", "file_id": file["id"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/")
def hello():
    return "✅ Hello from drive-api-hello via GitHub & Cloud Run!"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
