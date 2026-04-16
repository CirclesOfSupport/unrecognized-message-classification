import os
from flask import Flask, request, jsonify
from src.normalize import normalize_text

app = Flask(__name__)


@app.route("/", methods=["POST"])
def hello_webhook():
    """
    Minimal Cloud Run webhook endpoint.

    Expected input:
    {
        "user_input": "some text"
    }

    Returns:
    - original input
    - normalized input
    - simple status message
    """
    data = request.get_json(silent=True)

    user_text = data.get("user_input", "no input provided") if data else "no data"
    normalized_text = normalize_text(user_text)

    return jsonify(
        {
            "status": "received",
            "your_input_was": user_text,
            "normalized_input": normalized_text,
            "message": "Hello from Cloud Run!"
        }
    ), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)