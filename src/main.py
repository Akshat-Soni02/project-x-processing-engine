import os
from common.logging import get_logger, configure_logging
from pathlib import Path
from config.settings import APP_ENV, LOG_LEVEL

configure_logging(env=APP_ENV, level=LOG_LEVEL)
logger = get_logger(__name__)

project_root = Path(__file__).parent.parent
cred_path = project_root / "llm_credentials.json"
if cred_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    logger.info("Set GOOGLE_APPLICATION_CREDENTIALS from local file.")
else:
    logger.warning(
        "credentials.json not found; relying on Application Default Credentials or gcloud config."
    )

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


logger.info("Initialized STT, Smart, and Noteback providers")
logger.info("Initialized Vector Database")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Using push subscriptions - no listeners needed in the app.
    """
    # Startup
    logger.info("Application startup: ready to receive push subscription messages")

    try:
        yield

        # Shutdown
        logger.info("Application shutdown")

    except Exception as e:
        logger.critical(f"Critical error during startup/shutdown: {e}", exc_info=True)
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
        logger.error(f"Failed to parse request JSON: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON format"})

    if not envelope or "message" not in envelope:
        logger.error("Received an invalid Pub/Sub message format.")
        return JSONResponse(status_code=400, content={"error": "Invalid Pub/Sub message format"})

    try:
        message_data = envelope["message"].get("data")
        if not message_data:
            logger.error("Message data is missing")
            return JSONResponse(status_code=400, content={"error": "Message data is missing"})

        # Decode base64 message
        try:
            message_payload_str = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(message_payload_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to decode message: {e}")
            return JSONResponse(status_code=400, content={"error": "Invalid payload format"})

        # Extract data from payload
        data = payload.get("data", {})
        gcs_audio_url = data.get("gcs_audio_url")
        input_text = data.get("input_text")
        note_id = data.get("note_id")
        user_id = data.get("user_id")
        location = data.get("location")
        timestamp = data.get("timestamp")
        input_type = data.get("input_type")

        logger.debug(
            "Processing SMART branch message",
            extra={
                "note_id": note_id,
                "user_id": user_id,
                "input_type": input_type,
            },
        )

        # Get input data based on type
        input_data = None
        try:
            if input_type == User_Input_Type.AUDIO_WAV:
                if not gcs_audio_url:
                    logger.error("GCS audio URL is required for AUDIO_WAV input type")
                    return JSONResponse(
                        status_code=400, content={"error": "GCS audio URL required"}
                    )
                input_data = get_input_data(gcs_audio_url)
                if not input_data:
                    logger.error(f"Failed to fetch audio data from {gcs_audio_url}")
                    return JSONResponse(
                        status_code=400, content={"error": "Failed to fetch audio data"}
                    )

            elif input_type == User_Input_Type.TEXT_PLAIN:
                if not input_text:
                    logger.error("Input text is required for TEXT_PLAIN input type")
                    return JSONResponse(status_code=400, content={"error": "Input text required"})
                input_data = input_text
            else:
                logger.error(f"Unknown input type: {input_type}")
                return JSONResponse(
                    status_code=400, content={"error": f"Unknown input type: {input_type}"}
                )
        except Exception as e:
            logger.error(f"Error preparing input data: {e}", exc_info=True)
            return JSONResponse(status_code=500, content={"error": "Failed to prepare input data"})

        # Call run_smart
        try:
            response, metrics = run_smart(input_data)
            logger.info(
                f"[SMART] Processing completed. Response: {response is not None}, Metrics: {metrics is not None}"
            )

            if response is None:
                logger.warning("[SMART] Received None response from run_smart")
        except Exception as e:
            logger.error(f"[SMART] Error during processing: {e}", exc_info=True)
            response, metrics = None, None

        # Prepare upstream output
        upstream_output = {
            "note_id": note_id,
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "processed_output": response,
            "branch": "smart",
            "metrics": metrics,
        }

        logger.debug(f"Upstream output: {upstream_output}")

        # Send upstream
        # try:
        #     response = await upstream_call(upstream_output)
        #     logger.info("[SMART] Sent output upstream: {response}")
        # except Exception as e:
        #     logger.error(f"[SMART] Failed to send upstream: {e}", exc_info=True)

        return JSONResponse(status_code=200, content={"status": "ok", "branch": "smart"})

    except Exception as e:
        logger.error(f"[SMART] Unexpected error: {e}", exc_info=True)
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
        logger.error(f"Failed to parse request JSON: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON format"})

    if not envelope or "message" not in envelope:
        logger.error("Received an invalid Pub/Sub message format.")
        return JSONResponse(status_code=400, content={"error": "Invalid Pub/Sub message format"})

    try:
        message_data = envelope["message"].get("data")
        if not message_data:
            logger.error("Message data is missing")
            return JSONResponse(status_code=400, content={"error": "Message data is missing"})

        # Decode base64 message
        try:
            message_payload_str = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(message_payload_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to decode message: {e}")
            return JSONResponse(status_code=400, content={"error": "Invalid payload format"})

        # Extract data from payload
        data = payload.get("data", {})
        gcs_audio_url = data.get("gcs_audio_url")
        input_text = data.get("input_text")
        note_id = data.get("note_id")
        user_id = data.get("user_id")
        location = data.get("location")
        timestamp = data.get("timestamp")
        input_type = data.get("input_type")

        logger.debug(
            "Processing STT branch message",
            extra={
                "note_id": note_id,
                "user_id": user_id,
                "input_type": input_type,
            },
        )

        # Get input data based on type
        input_data = None
        try:
            if input_type == User_Input_Type.AUDIO_WAV:
                if not gcs_audio_url:
                    logger.error("GCS audio URL is required for AUDIO_WAV input type")
                    return JSONResponse(
                        status_code=400, content={"error": "GCS audio URL required"}
                    )
                input_data = get_input_data(gcs_audio_url)
                if not input_data:
                    logger.error(f"Failed to fetch audio data from {gcs_audio_url}")
                    return JSONResponse(
                        status_code=400, content={"error": "Failed to fetch audio data"}
                    )

            elif input_type == User_Input_Type.TEXT_PLAIN:
                if not input_text:
                    logger.error("Input text is required for TEXT_PLAIN input type")
                    return JSONResponse(status_code=400, content={"error": "Input text required"})
                input_data = input_text
            else:
                logger.error(f"Unknown input type: {input_type}")
                return JSONResponse(
                    status_code=400, content={"error": f"Unknown input type: {input_type}"}
                )
        except Exception as e:
            logger.error(f"Error preparing input data: {e}", exc_info=True)
            return JSONResponse(status_code=500, content={"error": "Failed to prepare input data"})

        # Call run_stt
        try:
            response, metrics = run_stt(input_data)
            logger.info(
                f"[STT] Processing completed. Response: {response is not None}, Metrics: {metrics is not None}"
            )

            if response is None:
                logger.warning("[STT] Received None response from run_stt")
        except Exception as e:
            logger.error(f"[STT] Error during processing: {e}", exc_info=True)
            response, metrics = None, None

        # Prepare upstream output
        upstream_output = {
            "note_id": note_id,
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "processed_output": response,
            "branch": "stt",
            "metrics": metrics,
        }

        logger.debug(f"Upstream output: {upstream_output}")

        # Send upstream
        # try:
        #     response = await upstream_call(upstream_output)
        #     logger.info(f"[STT] Sent output upstream: {response}")
        # except Exception as e:
        #     logger.error(f"[STT] Failed to send upstream: {e}", exc_info=True)

        return JSONResponse(status_code=200, content={"status": "ok", "branch": "stt"})

    except Exception as e:
        logger.error(f"[STT] Unexpected error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# Server health check endpoint
@app.get("/health")
def health():
    logger.info("Health check working")
    return {"status": "ok"}


@app.post("/processed-output")
async def upstream_call(request: Request):
    data = await request.json()
    logger.info(f"Upstream call working: {data}")
    return {"status": "ok"}
