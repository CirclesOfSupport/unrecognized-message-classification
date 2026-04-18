CONTAINER ?= classifier-74671951247.us-central1.run.app
IMAGE_NAME ?= gcr.io/$(CONTAINER)

.PHONY: build
build:
	gcloud builds submit --tag gcr.io/classify-unknown-messages/classifier
	gcloud run deploy classifier   --image gcr.io/classify-unknown-messages/classifier   --platform managed   --region us-central1   --allow-unauthenticated   --port 8081
	gcloud run services update classifier   --region us-central1   --set-env-vars SECRET_TOKEN=easy_alert

.PHONY: test
test:
	curl -X POST https://classifier-74671951247.us-central1.run.app/classify   -H "Content-Type: application/json"   -H "Authorization: Bearer $(gcloud auth print-identity-token)" -H "X-Secret-Token: easy_alert"  -d '{"input_text": "thanks so much"}'