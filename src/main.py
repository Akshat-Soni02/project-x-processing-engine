"""
Main entry point for the Arilo Processing Engine FastAPI application.
Handles Pub/Sub push subscriptions for STT and SMART processing branches.
"""

import os
import base64
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google import genai

from common.logging import get_logger, configure_logging
from common.utils import get_input_data
from config.settings import APP_ENV, LOG_LEVEL, GCP_PROJECT_ID, GCP_LOCATION, ENABLE_VERTEX_AI
from config.config import User_Input_Type, Pipeline
from db.db import Database
from impl.gemini import GeminiProvider
from pipeline.stt import SttPipeline
from pipeline.smart import SmartPipeline

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Resets or initializes global resources if required.
    """
    # Startup
    logger.info("Application startup initiated")

    # Initialize Database
    try:
        app.state.vector_db = Database()
        logger.info("Vector Database initialized")
    except Exception as e:
        logger.critical("Failed to initialize Vector Database", extra={"error": str(e)})
        raise

    # Initialize LLM Client and Pipelines
    try:
        gemini_client = genai.Client(
            vertexai=ENABLE_VERTEX_AI, project=GCP_PROJECT_ID, location=GCP_LOCATION
        )
        logger.debug("Vertex AI Gemini Client initialized")

        # Create providers
        stt_provider = GeminiProvider(gemini_client)
        smart_provider = GeminiProvider(gemini_client)
        noteback_provider = GeminiProvider(gemini_client)

        # Initialize Pipelines
        app.state.stt_pipeline = SttPipeline(stt_provider)
        app.state.smart_pipeline = SmartPipeline(
            smart_provider, noteback_provider, app.state.vector_db
        )
        logger.info("Processing pipelines initialized")

    except Exception as e:
        logger.critical("Failed to initialize Pipelines", extra={"error": str(e)})
        raise

    logger.info("Application startup complete: ready to receive messages")

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


async def process_pipeline_request(request: Request, pipeline_type: Pipeline):
    """
    Common wrapper for handling pipeline requests.
    Parses Pub/Sub message, prepares input, and triggers the specified pipeline.
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

        # Context for the pipeline
        context = {
            "note_id": note_id,
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "input_type": input_type,
        }

        logger.debug(
            "Processing request",
            extra={"note_id": note_id, "user_id": user_id, "branch": pipeline_type.value},
        )

        # Prepare Input Data
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

        # Run Pipeline
        if pipeline_type == Pipeline.SMART:
            request.app.state.smart_pipeline.run(input_data, context)
        elif pipeline_type == Pipeline.STT:
            request.app.state.stt_pipeline.run(input_data, context)
        else:
            logger.error("Unknown pipeline type requested", extra={"type": pipeline_type})
            return JSONResponse(status_code=400, content={"error": "Unknown pipeline type"})

        return JSONResponse(
            status_code=200, content={"status": "ok", "branch": pipeline_type.value}
        )

    except Exception as e:
        logger.critical(
            "Unexpected error in request handler",
            extra={"error": str(e), "branch": pipeline_type.value},
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.post("/branch/subcription/smart")
async def smart_branch(request: Request):
    """
    Handle push subscription messages from Pub/Sub for SMART branch.
    """
    return await process_pipeline_request(request, Pipeline.SMART)


@app.post("/branch/subcription/stt")
async def stt_branch(request: Request):
    """
    Handle push subscription messages from Pub/Sub for STT branch.
    """
    return await process_pipeline_request(request, Pipeline.STT)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/processed-output")
async def upstream_call_endpoint(request: Request):
    """
    Mock upstream endpoint for testing callbacks.
    """
    data = await request.json()
    logger.debug("Upstream processed output received", extra={"data": data})
    return {"status": "ok"}
