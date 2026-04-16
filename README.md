# String-Bucketing-Classifier
Classifier for unknown/unrecognized messages

curl -X POST https://classifier-74671951247.us-central1.run.app/classify   -H "Content-Type: application/json"   -H "Authorization: Bearer $(gcloud auth print-identity-token)"   -d '{"input_text": "thanks so much"}'