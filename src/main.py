from typing import Dict, Any,Optional
from contextlib import asynccontextmanager 
import threading
from datetime import datetime

from fastapi.responses import JSONResponse
from fastapi import FastAPI, UploadFile, File,HTTPException, status
from pydantic import BaseModel,Field,field_validator

from services.pubsub.pubsub_service import PubSubService
from common.logging import get_logger, configure_logging
from config.settings import ARILO_SUBSCRIPTION_ID,SMART_SUBSCRIPTION_ID ,APP_ENV, LOG_LEVEL

# Configure logging
configure_logging(env=APP_ENV, level=LOG_LEVEL)
logger = get_logger(__name__)

# Global state
services: Dict[str, PubSubService] = {}
listener_futures: Dict[str, Optional[Any]] = {"stt": None, "smart": None}


@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Handles Pub/Sub listener initialization and cleanup.
    """
    # Startup
    logger.info("Application startup: initializing Pub/Sub service")
    
    try:
       # ensure these come from config.settings
        services["stt"] = PubSubService(SUBSCRIPTION_ID=ARILO_SUBSCRIPTION_ID,NAME="stt")
        services["smart"] = PubSubService(SUBSCRIPTION_ID=SMART_SUBSCRIPTION_ID,NAME="smart")

        def run_listener(label: str):
            try:
                future = services[label].start_listener()
                listener_futures[label] = future
                future.result()
            except Exception as e:
                logger.error(f"Listener error ({label}): {e}", exc_info=True)
                
        threading.Thread(target=run_listener, args=("stt",), daemon=True).start()
        threading.Thread(target=run_listener, args=("smart",), daemon=True).start()
        logger.info("Pub/Sub listeners started: stt, smart")
        logger.info("Starting listeners",
            extra={
              "stt_subscription": services["stt"].subscription_path,
              "smart_subscription": services["smart"].subscription_path,
            })

        yield

    # Shutdown
        logger.info("Shutdown: stopping Pub/Sub listeners")
        for label, svc in services.items():
            try:
                svc.stop_listener(listener_futures.get(label))
                logger.info(f"Stopped listener: {label}")
            except Exception as e:
                logger.error(f"Error stopping listener ({label}): {e}", exc_info=True)

    except Exception as e:
        logger.critical(f"Critical error during startup/shutdown: {e}", exc_info=True)
        raise
    
app = FastAPI(
    title="Arilo Processing Engine",
    description="Audio processing engine with Google Cloud Pub/Sub integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Server health check endpoint
@app.get("/health")
def health():
    logger.info("Health check working")
    return {"status": "ok"}


