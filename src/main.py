# src/main.py
import logging
from pathlib import Path
import os

from flask import Flask, request, jsonify

from src.normalize import NormalizedText
from src.classifier import KeywordClassifier, RegexClassifier
from src.utils import bucket_loader

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "")


def classify_text(raw_text: str) -> dict:
    normalized = NormalizedText(raw_text)
    buckets = bucket_loader(Path("config"))
    classifiers = [KeywordClassifier(), RegexClassifier()]

    for bucket in buckets:
        for classifier in classifiers:
            result = classifier.classify(normalized, bucket)
            if result.matched:
                return {
                    "matched": True,
                    "bucket": bucket.name,
                    "priority": bucket.priority,
                    "classifier": classifier.layer_name,
                    "rule_name": result.rule_name,
                    "details": result.details,
                    "raw_text": normalized.raw_text,
                    "normalized_text": normalized.normalized_text,
                    "emoji_normalized_text": normalized.emoji_normalized_text,
                }

    return {
        "matched": False,
        "bucket": "other",
        "raw_text": normalized.raw_text,
        "normalized_text": normalized.normalized_text,
        "emoji_normalized_text": normalized.emoji_normalized_text,
    }


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


@app.route("/classify", methods=["POST"])
def classify():
    if not request.is_json:
        return jsonify({"error": "Request must be application/json"}), 400

    payload = request.get_json(silent=True) or {}
    input_text = payload.get("input_text")
    token = request.headers.get("X-Secret-Token", "")
    
    if token != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if not input_text or not isinstance(input_text, str):
        return jsonify({"error": "JSON body must include string field 'input_text'"}), 400

    try:
        result = classify_text(input_text)
        return jsonify(result), 200
    except Exception as e:
        logging.exception("Classification failed")
        return jsonify({"error": str(e)}), 500