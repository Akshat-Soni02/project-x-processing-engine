import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "documind-474519")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
PUBSUB_TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID", "arilo-llm-topic")
PUBSUB_SERVICE_ACCOUNT_PATH = os.getenv("PUBSUB_SERVICE_ACCOUNT_PATH", "")
ARILO_SUBSCRIPTION_ID = os.getenv("ARILO_SUBSCRIPTION_ID", "arilo-llm-subscription")
SMART_SUBSCRIPTION_ID = os.getenv("SMART_SUBSCRIPTION_ID", "smart-llm-subscription")

required_vars = [
    "GCP_PROJECT_ID",
    "ARILO_SUBSCRIPTION_ID",
    "SMART_SUBSCRIPTION_ID",
    "PUBSUB_SERVICE_ACCOUNT_PATH"
]

for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")