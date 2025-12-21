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
from common.utils import get_gcs_data
from config.settings import (
    APP_ENV,
    LOG_LEVEL,
    GCP_PROJECT_ID,
    GCP_LOCATION,
    ENABLE_VERTEX_AI,
    MAX_PIPELINE_STAGE_ATTEMPTS,
)
from config.config import User_Input_Type, Pipeline, Pipeline_Stage_Status, Pipeline_Stage_Errors
from db.db import Database
from impl.gemini import GeminiProvider
from pipeline.stt import SttPipeline
from pipeline.smart import SmartPipeline
from pipeline.exceptions import FatalPipelineError, TransientPipelineError
from util.util import upstream_call

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


from fastapi.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup/shutdown).
    Resets or initializes global resources if required.
    """
    # Startup
    logger.info("Application startup initiated")

    try:
        app.state.vector_db = Database()
        logger.info("Vector Database initialized")
    except Exception as e:
        logger.critical("Failed to initialize Vector Database", extra={"error": str(e)})
        raise

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
        app.state.stt_pipeline = SttPipeline(stt_provider, app.state.vector_db)
        app.state.smart_pipeline = SmartPipeline(
            smart_provider, noteback_provider, app.state.vector_db
        )
        logger.info("Processing pipelines initialized")
    except Exception as e:
        logger.critical("Failed to initialize Pipelines", extra={"error": str(e)})
        raise

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutdown initiated")
    try:
        app.state.vector_db.close()
    except Exception as e:
        logger.error("Error during database shutdown", extra={"error": str(e)})
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Arilo Processing Engine",
    description="Audio processing engine with Google Cloud Pub/Sub integration",
    version="1.0.0",
    lifespan=lifespan,
)


async def _parse_pubsub_payload(request: Request) -> dict:
    """
    Extracts and decodes the Pub/Sub message payload.
    """
    try:
        envelope = await request.json()
    except Exception as e:
        logger.error("Failed to parse request JSON", extra={"error": str(e)})
        return None

    if not envelope or "message" not in envelope:
        logger.warning("Invalid Pub/Sub message format")
        return None

    message_data = envelope["message"].get("data")
    if not message_data:
        logger.warning("Message data is missing in Pub/Sub envelope")
        return None

    try:
        message_payload_str = base64.b64decode(message_data).decode("utf-8")
        return json.loads(message_payload_str)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to decode message payload", extra={"error": str(e)})
        return None


def _send_upstream_status(
    data: dict,
    context: dict,
    pipeline_type: Pipeline,
    status: Pipeline_Stage_Status,
    output=None,
    error=None,
):
    """
    Helper to format and send status updates upstream.
    """
    try:
        upstream_call(
            {
                "job_id": data.get("job_id"),
                "note_id": data.get("note_id"),
                "user_id": data.get("user_id"),
                "location": data.get("location"),
                "timestamp": data.get("timestamp"),
                "input_type": data.get("input_type"),
                "output": output,
                "error": str(error) if error else None,
                "pipeline_stage": pipeline_type.value,
                "status": status.value,
            }
        )
    except Exception as e:
        logger.error("Failed to send upstream update", extra={"error": str(e)})


def _handle_stage_checkout(db: Database, pipeline_type: Pipeline, data: dict, context: dict):
    """
    Checks the database for the current stage status and determines if processing should proceed.
    Returns (pipeline_stage_id, None) if okay to proceed.
    Returns (None, JSONResponse) if processing should stop (ACK/Ignore).
    """
    job_id = data.get("job_id")
    pipeline_name = pipeline_type.value

    try:
        pipeline_stage = db.read_stage(job_id, pipeline_name)
    except Exception as e:
        logger.error("Failed to read stage", extra={"error": str(e)})
        return None, JSONResponse(
            status_code=200, content={"error": "Ignored request, failed to read stage"}
        )

    if pipeline_stage is None:
        logger.warning(
            "Request ignored, pipeline stage not found",
            extra={"job_id": job_id, "pipeline": pipeline_name},
        )
        return None, JSONResponse(
            status_code=200, content={"error": "Ignored request, pipeline stage not found"}
        )

    pipeline_stage_id = pipeline_stage.get("id")

    # Ignore if already in progress
    if pipeline_stage.get("status") == Pipeline_Stage_Status.IN_PROGRESS:
        logger.warning(
            "Request ignored, pipeline stage already in progress", extra={"job_id": job_id}
        )
        return None, JSONResponse(
            status_code=200,
            content={"error": "Ignored request, pipeline stage already in progress"},
        )

    # Ignore if already completed, Just send the output back to upstream
    if pipeline_stage.get("status") == Pipeline_Stage_Status.COMPLETED:
        logger.warning(
            "Request ignored, pipeline stage already completed. Sending output upstream",
            extra={"job_id": job_id},
        )
        try:
            output = db.read_stage_output(pipeline_stage_id)
            if output:
                _send_upstream_status(
                    data, context, pipeline_type, Pipeline_Stage_Status.COMPLETED, output=output
                )
                return None, JSONResponse(
                    status_code=200,
                    content={"error": "Ignored request, pipeline stage already completed"},
                )
            else:
                logger.warning(
                    "Pipeline stage marked COMPLETED but output not found. Proceeding with re-run."
                )
        except Exception as e:
            logger.error("Failed to process completed stage output", extra={"error": str(e)})
            return None, JSONResponse(
                status_code=400, content={"error": "Failed to handle completed stage output"}
            )

    print(pipeline_stage)

    # Ignore if attempt count exceeded
    if pipeline_stage.get("attempt_count") >= MAX_PIPELINE_STAGE_ATTEMPTS:
        logger.warning(
            "Request ignored, attempt count exceeded",
            extra={
                "job_id": job_id,
                "attempts": pipeline_stage.get("attempt_count"),
                "max": MAX_PIPELINE_STAGE_ATTEMPTS,
            },
        )
        try:
            db.update_pipeline_stage_status(pipeline_stage_id, Pipeline_Stage_Status.FAILED)
            db.update_pipeline_stage_error(
                pipeline_stage_id, Pipeline_Stage_Errors.ATTEMPT_COUNT_EXCEEDED
            )
            _send_upstream_status(
                data,
                context,
                pipeline_type,
                Pipeline_Stage_Status.FAILED,
                error=Pipeline_Stage_Errors.ATTEMPT_COUNT_EXCEEDED,
            )
        except Exception as e:
            logger.error("Failed to mark stage as failed on max attempts", extra={"error": str(e)})

        return None, JSONResponse(
            status_code=200,
            content={"error": "Ignored request, pipeline stage attempt count exceeded"},
        )

    # Update status and increment attempt count
    try:
        db.update_pipeline_stage_status(pipeline_stage_id, Pipeline_Stage_Status.IN_PROGRESS)
        db.increment_pipeline_stage_attempt_count(pipeline_stage_id)
    except Exception as e:
        logger.error("Failed to update stage to IN_PROGRESS", extra={"error": str(e)})

    return pipeline_stage_id, None


def _get_pipeline_input(input_type: str, data: dict):
    """
    Prepares the input data (audio bytes or text) based on input type.
    Returns (input_data, error_msg)
    """
    gcs_audio_url = data.get("gcs_audio_url")
    input_text = data.get("input_text")

    if input_type == User_Input_Type.AUDIO_WAV:
        if not gcs_audio_url:
            return None, "Ignored missing audio URL, required for this input type"
        audio_data = get_gcs_data(gcs_audio_url)
        if not audio_data:
            return None, "failed to fetch audio data"
        return audio_data, None

    elif input_type == User_Input_Type.TEXT_PLAIN:
        if not input_text:
            return None, "Ignored missing input text, required for this input type"
        return input_text, None

    return None, f"Ignored unknown input type: {input_type}"


async def process_pipeline_request(request: Request, pipeline_type: Pipeline):
    """
    Common wrapper for handling pipeline requests.
    Parses Pub/Sub message, prepares input, and triggers the specified pipeline.
    """
    try:
        payload = await _parse_pubsub_payload(request)
        if payload is None:
            return JSONResponse(
                status_code=200, content={"error": "Ignored invalid message format"}
            )

        data = payload.get("data", {})
        context = {
            "job_id": data.get("job_id"),
            "note_id": data.get("note_id"),
            "user_id": data.get("user_id"),
            "location": data.get("location"),
            "timestamp": data.get("timestamp"),
            "input_type": data.get("input_type"),
        }

        # DB Stage Handling and Checkout
        pipeline_stage_id, early_response = _handle_stage_checkout(
            request.app.state.vector_db, pipeline_type, data, context
        )
        if early_response:
            return early_response

        context["pipeline_stage_id"] = pipeline_stage_id

        # Prepare Input Data
        input_data, error_msg = _get_pipeline_input(context["input_type"], data)
        if error_msg:
            logger.error(error_msg)
            # 400 for structural fetch failures, 200 for validation logic
            status_code = 400 if "fetch" in error_msg.lower() else 200
            return JSONResponse(status_code=status_code, content={"error": error_msg})

        # Execute Pipeline Task using run_in_threadpool
        try:
            if pipeline_type == Pipeline.SMART:
                await run_in_threadpool(request.app.state.smart_pipeline.run, input_data, context)
            elif pipeline_type == Pipeline.STT:
                await run_in_threadpool(request.app.state.stt_pipeline.run, input_data, context)
            else:
                return JSONResponse(
                    status_code=200, content={"error": "Dropped unknown pipeline type"}
                )

            return JSONResponse(
                status_code=200, content={"status": "ok", "branch": pipeline_type.value}
            )

        except FatalPipelineError as e:
            logger.error(
                "Fatal pipeline error, acking message", extra={"error": str(e)}, exc_info=True
            )
            request.app.state.vector_db.update_pipeline_stage_status(
                context["pipeline_stage_id"], pipeline_type.value, Pipeline_Stage_Status.FAILED
            )
            request.app.state.vector_db.update_pipeline_stage_error(
                context["pipeline_stage_id"],
                pipeline_type.value,
                Pipeline_Stage_Errors.FATAL_PIPELINE_ERROR,
            )
            _send_upstream_status(
                data, context, pipeline_type, Pipeline_Stage_Status.FAILED, error=e
            )
            return JSONResponse(
                status_code=200, content={"status": "fatal_pipeline_error", "message": str(e)}
            )

        except TransientPipelineError as e:
            logger.warning(
                "Transient pipeline error, retrying message", extra={"error": str(e)}, exc_info=True
            )
            return JSONResponse(status_code=503, content={"status": "transient_pipeline_error"})

    except Exception as e:
        logger.critical(
            "Unexpected error in request handler", extra={"error": str(e)}, exc_info=True
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
