from typing import Dict, Any,Optional
from contextlib import asynccontextmanager 
import threading
from datetime import datetime

from fastapi.responses import JSONResponse
from fastapi import FastAPI, UploadFile, File,HTTPException, status
from pydantic import BaseModel,Field,field_validator

from services.pubsub.pubsub_service import PubSubService
from common.logging import get_logger, configure_logging
from config.settings import ARILO_SUBSCRIPTION_ID, APP_ENV, LOG_LEVEL

# Configure logging
configure_logging(env=APP_ENV, level=LOG_LEVEL)
logger = get_logger(__name__)

# Global state
listener_future = None
pubsub_service = PubSubService(SUBSCRIPTION_ID=ARILO_SUBSCRIPTION_ID)

@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Handles Pub/Sub listener initialization and cleanup.
    """
    global _listener_future, _pubsub_service
    
    # Startup
    logger.info("Application startup: initializing Pub/Sub service")
    
    try:
        pubsub_service = PubSubService(SUBSCRIPTION_ID=ARILO_SUBSCRIPTION_ID)

        def run_listener():
            global listener_future
            listener_future = pubsub_service.start_listener()
            try:
                listener_future.result()
            except Exception as e:
                logger.error(f"Listener error: {e}")
        listener_thread = threading.Thread(target=run_listener, daemon=True)
        listener_thread.start()
        logger.info("Pub/Sub listener started.")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    yield
    # Shutdown
    logger.info("Application shutdown: stopping Pub/Sub listener")
    if pubsub_service:
        pubsub_service.stop_listener(listener_future)
        logger.info("Pub/Sub listener stopped.")
    
app = FastAPI(
    title="Arilo Processing Engine",
    description="Audio processing engine with Google Cloud Pub/Sub integration",
    version="1.0.0",
    lifespan=lifespan,
)

@app.post("/publish")
async def publish_message(data: dict, attributes: Dict[str, str] | None = None):
    """Publish a message to Pub/Sub with optional attributes."""
    try:
        message_id = pubsub_service.publish_message(data, attributes=attributes or {})
        return {"status": "success", "message_id": message_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Server health check endpoint
@app.get("/health")
def health():
    logger.info("Health check working")
    return {"status": "ok"}


