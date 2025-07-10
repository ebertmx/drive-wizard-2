import os
from flask import Flask

app = Flask(__name__)

# This will print when the container starts.
print("--- MINIMAL APP STARTING ---")

@app.route('/')
def hello():
    """A simple hello world endpoint."""
    print("--- 'Hello World' endpoint was called ---")
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))