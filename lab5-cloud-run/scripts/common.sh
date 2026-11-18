# Sourced by the other scripts. Fixed lab values, same as deploy/config.py.
PROJECT=boston-resilience-twin
REGION=us-east1
REGISTRY_HOST=us-east1-docker.pkg.dev
REPO=lab5
SERVICE=lab5-forecast
BASELINE_SERVICE=lab5-hello
SA_NAME=lab5-run
SA_EMAIL=${SA_NAME}@${PROJECT}.iam.gserviceaccount.com
IMAGE_NAME=${REGISTRY_HOST}/${PROJECT}/${REPO}/forecast
