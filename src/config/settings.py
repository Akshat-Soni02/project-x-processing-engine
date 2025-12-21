"""
Application-wide settings and environment variable management.
Loads configuration from .env and validates presence of critical variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "documind-474519")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
ENABLE_VERTEX_AI = os.getenv("ENABLE_VERTEX_AI", "true").lower() == "true"
PUBSUB_SERVICE_ACCOUNT_PATH = os.getenv("PUBSUB_SERVICE_ACCOUNT_PATH", "")
LLM_SERVICE_ACCOUNT_PATH = os.getenv("LLM_SERVICE_ACCOUNT_PATH", "")
GCS_SERVICE_ACCOUNT_PATH = os.getenv("GCS_SERVICE_ACCOUNT_PATH", "")
UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://localhost:8080")

MAX_PIPELINE_STAGE_ATTEMPTS = int(os.getenv("MAX_PIPELINE_STAGE_ATTEMPTS", "3") or "3")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433") or "5433")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mypassword")
DB_NAME = os.getenv("DB_NAME", "mydb")


required_vars = [
    "GCP_PROJECT_ID",
    "PUBSUB_SERVICE_ACCOUNT_PATH",
    "LLM_SERVICE_ACCOUNT_PATH",
    "GCS_SERVICE_ACCOUNT_PATH",
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
]

for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")
