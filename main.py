import os
from flask import Flask, request, jsonify
from google.auth import default
from googleapiclient.discovery import build

app = Flask(__name__)

def get_drive_service():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

@app.route("/drive/read", methods=["POST"])
def read_file():
    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Missing 'filename'"}), 400

    try:
        drive = get_drive_service()

        # Search for file by name
        results = drive.files().list(
            q=f"name = '{filename}' and trashed = false",
            fields="files(id, name)",
            pageSize=1
        ).execute()

        files = results.get("files", [])
        if not files:
            return jsonify({"error": f"File '{filename}' not found"}), 404

        file_id = files[0]["id"]

        # Download file content
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

@app.route("/")
def hello():
    return "✅ Hello from drive-api-hello via GitHub & Cloud Run!"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
