"""
Main entry point for the Arilo Processing Engine FastAPI application.
Handles Pub/Sub push subscriptions for STT and SMART processing branches.
"""

import os
from common.logging import get_logger, configure_logging
from pathlib import Path
from config.settings import APP_ENV, LOG_LEVEL

# Configure logging
configure_logging(env=APP_ENV, level=LOG_LEVEL)
logger = get_logger(__name__)

# Credentials configuration
project_root = Path(__file__).parent.parent
cred_path = project_root / "llm_credentials.json"
if cred_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    logger.debug("Application credentials loaded from local file")
else:
    logger.warning("Application credentials file not found")

import base64
import json
from common.utils import get_input_data
from config.config import User_Input_Type
from services.llm.llm_service import run_smart, run_stt

from fastapi import Request


from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from services.pubsub.pubsub_service import PubSubService


# Global state
services: Dict[str, PubSubService] = {}
listener_futures: Dict[str, Optional[Any]] = {"stt": None, "smart": None}

# vertexai.init(project=Project.PROJECT_ID, location=Project.LOCATION)


logger.debug("Services initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Resets or initializes global resources if required.
    """
    # Startup
    logger.info("Application startup successfully: ready to receive messages")

    try:
        yield
        logger.info("Application shutdown")
    except Exception as e:
        logger.critical(
            "Error during application lifecycle", extra={"error": str(e)}, exc_info=True
        )
        raise


app = FastAPI(
    title="Arilo Processing Engine",
    description="Audio processing engine with Google Cloud Pub/Sub integration",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/smart-branch-subscription")
async def smart_branch(request: Request):
    """
    Handle push subscription messages from Pub/Sub for SMART branch.
    Decodes base64 message, extracts data, calls run_smart, and sends upstream.
    """
    try:
        envelope = await request.json()
    except Exception as e:
        logger.error("Failed to parse request JSON", extra={"error": str(e)})
        return JSONResponse(status_code=400, content={"error": "Invalid JSON format"})

    if not envelope or "message" not in envelope:
        logger.warning("Invalid Pub/Sub message format")
        return JSONResponse(status_code=400, content={"error": "Invalid Pub/Sub message format"})

    try:
        message_data = envelope["message"].get("data")
        if not message_data:
            logger.warning("Message data is missing in Pub/Sub envelope")
            return JSONResponse(status_code=400, content={"error": "Message data is missing"})

        try:
            message_payload_str = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(message_payload_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Failed to decode message payload", extra={"error": str(e)})
            return JSONResponse(status_code=400, content={"error": "Invalid payload format"})

        data = payload.get("data", {})
        gcs_audio_url = data.get("gcs_audio_url")
        input_text = data.get("input_text")
        note_id = data.get("note_id")
        user_id = data.get("user_id")
        location = data.get("location")
        timestamp = data.get("timestamp")
        input_type = data.get("input_type")

        logger.debug(
            "Processing request", extra={"note_id": note_id, "user_id": user_id, "branch": "smart"}
        )

        input_data = None
        try:
            if input_type == User_Input_Type.AUDIO_WAV:
                if not gcs_audio_url:
                    logger.error("Audio URL required for this input type")
                    return JSONResponse(
                        status_code=400, content={"error": "GCS audio URL required"}
                    )
                input_data = get_input_data(gcs_audio_url)
                if not input_data:
                    logger.error("Failed to fetch audio data", extra={"url": gcs_audio_url})
                    return JSONResponse(
                        status_code=400, content={"error": "Failed to fetch audio data"}
                    )
            elif input_type == User_Input_Type.TEXT_PLAIN:
                if not input_text:
                    logger.error("Input text required for this input type")
                    return JSONResponse(status_code=400, content={"error": "Input text required"})
                input_data = input_text
            else:
                logger.error("Unsupported input type", extra={"input_type": input_type})
                return JSONResponse(
                    status_code=400, content={"error": f"Unknown input type: {input_type}"}
                )
        except Exception as e:
            logger.error("Error preparing input data", extra={"error": str(e)}, exc_info=True)
            return JSONResponse(status_code=500, content={"error": "Failed to prepare input data"})

        try:
            logger.info(
                "Starting processing pipeline",
                extra={"branch": "smart", "user_id": user_id, "note_id": note_id},
            )
            response, metrics = run_smart(input_data)
            logger.info(
                "Processing pipeline completed", extra={"branch": "smart", "user_id": user_id}
            )
            logger.debug(
                "Pipeline output metrics",
                extra={
                    "response_present": response is not None,
                    "metrics_present": metrics is not None,
                },
            )
            if response is None:
                logger.warning("Empty response received from pipeline", extra={"branch": "smart"})
        except Exception as e:
            logger.critical(
                "Critical error during processing",
                extra={"error": str(e), "branch": "smart"},
                exc_info=True,
            )
            response, metrics = None, None

        upstream_output = {
            "note_id": note_id,
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "processed_output": response,
            "branch": "smart",
            "metrics": metrics,
        }
        logger.debug("Request details", extra={"output": upstream_output})
        return JSONResponse(status_code=200, content={"status": "ok", "branch": "smart"})

    except Exception as e:
        logger.critical(
            "Unexpected error in request handler",
            extra={"error": str(e), "branch": "smart"},
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.post("/stt-branch-subscription")
async def stt_branch(request: Request):
    """
    Handle push subscription messages from Pub/Sub for STT branch.
    Decodes base64 message, extracts data, calls run_stt, and sends upstream.
    """
    try:
        envelope = await request.json()
    except Exception as e:
        logger.error("Failed to parse request JSON", extra={"error": str(e)})
        return JSONResponse(status_code=400, content={"error": "Invalid JSON format"})

    if not envelope or "message" not in envelope:
        logger.warning("Invalid Pub/Sub message format")
        return JSONResponse(status_code=400, content={"error": "Invalid Pub/Sub message format"})

    try:
        message_data = envelope["message"].get("data")
        if not message_data:
            logger.warning("Message data is missing in Pub/Sub envelope")
            return JSONResponse(status_code=400, content={"error": "Message data is missing"})

        try:
            message_payload_str = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(message_payload_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Failed to decode message payload", extra={"error": str(e)})
            return JSONResponse(status_code=400, content={"error": "Invalid payload format"})

        data = payload.get("data", {})
        gcs_audio_url = data.get("gcs_audio_url")
        input_text = data.get("input_text")
        note_id = data.get("note_id")
        user_id = data.get("user_id")
        location = data.get("location")
        timestamp = data.get("timestamp")
        input_type = data.get("input_type")

        logger.debug(
            "Processing request", extra={"note_id": note_id, "user_id": user_id, "branch": "stt"}
        )

        input_data = None
        try:
            if input_type == User_Input_Type.AUDIO_WAV:
                if not gcs_audio_url:
                    logger.warning("Audio URL missing for this input type")
                    return JSONResponse(
                        status_code=400, content={"error": "GCS audio URL required"}
                    )
                input_data = get_input_data(gcs_audio_url)
                if not input_data:
                    logger.error("Failed to fetch audio data", extra={"url": gcs_audio_url})
                    return JSONResponse(
                        status_code=400, content={"error": "Failed to fetch audio data"}
                    )
            elif input_type == User_Input_Type.TEXT_PLAIN:
                if not input_text:
                    logger.warning("Input text missing for this input type")
                    return JSONResponse(status_code=400, content={"error": "Input text required"})
                input_data = input_text
            else:
                logger.warning("Unsupported input type", extra={"input_type": input_type})
                return JSONResponse(
                    status_code=400, content={"error": f"Unknown input type: {input_type}"}
                )
        except Exception as e:
            logger.error("Error preparing input data", extra={"error": str(e)}, exc_info=True)
            return JSONResponse(status_code=500, content={"error": "Failed to prepare input data"})

        try:
            logger.info(
                "Starting processing pipeline",
                extra={"branch": "stt", "user_id": user_id, "note_id": note_id},
            )
            response, metrics = run_stt(input_data)
            logger.info(
                "Processing pipeline completed", extra={"branch": "stt", "user_id": user_id}
            )
            logger.debug(
                "Pipeline output metrics",
                extra={
                    "response_present": response is not None,
                    "metrics_present": metrics is not None,
                },
            )
            if response is None:
                logger.warning("Empty response received from pipeline", extra={"branch": "stt"})
        except Exception as e:
            logger.critical(
                "Critical error during processing",
                extra={"error": str(e), "branch": "stt"},
                exc_info=True,
            )
            response, metrics = None, None

        upstream_output = {
            "note_id": note_id,
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "processed_output": response,
            "branch": "stt",
            "metrics": metrics,
        }
        logger.debug("Request details", extra={"output": upstream_output})
        return JSONResponse(status_code=200, content={"status": "ok", "branch": "stt"})

    except Exception as e:
        logger.critical(
            "Unexpected error in request handler",
            extra={"error": str(e), "branch": "stt"},
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/processed-output")
async def upstream_call(request: Request):
    data = await request.json()
    logger.debug("Upstream processed output received", extra={"data": data})
    return {"status": "ok"}
