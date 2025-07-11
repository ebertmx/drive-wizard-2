import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    # Change the message below
    return "Hello from GitHub! The trigger works!"



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))