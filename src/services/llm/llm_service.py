"""
High-level LLM orchestration service.
Initializes Gemini clients and provides entry points for STT and SMART processing pipelines.
"""

from common.logging import get_logger
from google import genai
from config.config import User_Input_Type
from config.settings import GCP_PROJECT_ID, GCP_LOCATION, ENABLE_VERTEX_AI
from impl.gemini import GeminiProvider
from impl.llm_branches import stt_branch, smart_branch
from vector.db import Database

logger = get_logger(__name__)
vector_db = Database()

# Initialize Gemini client
gemini_client = genai.Client(
    vertexai=ENABLE_VERTEX_AI, project=GCP_PROJECT_ID, location=GCP_LOCATION
)
logger.debug("Initialized Vertex AI Gemini Client")

# Create stateless provider instances
stt_provider = GeminiProvider(gemini_client)
smart_provider = GeminiProvider(gemini_client)
noteback_provider = GeminiProvider(gemini_client)


def run_stt(input_data: bytes):
    """
    Execute the Speech-to-Text pipeline.

    Args:
        input_data (bytes): Raw audio data to process.

    Returns:
        tuple: (response_dict, metrics_dict) or None if processing fails.
    """
    if input_data is None or len(input_data) == 0:
        logger.warning("Pipeline execution skipped: No input data")
        return None

    try:
        response, metrics = stt_branch(stt_provider, input_data, User_Input_Type.AUDIO_WAV)
        return response, metrics
    except Exception as e:
        logger.critical("Pipeline execution failed", extra={"error": str(e)}, exc_info=True)
        return None


def run_smart(input_data: bytes):
    """
    Execute the SMART processing pipeline (Context + Noteback).

    Args:
        input_data (bytes/str): Input data to process (audio or text depending on branch config).

    Returns:
        tuple: (response_dict, metrics_dict) or None if processing fails.
    """
    if input_data is None or len(input_data) == 0:
        logger.warning("Pipeline execution skipped: No input data")
        return None

    try:
        response, metrics = smart_branch(
            smart_provider, noteback_provider, vector_db, input_data, User_Input_Type.AUDIO_WAV
        )
        return response, metrics
    except Exception as e:
        logger.critical("Pipeline execution failed", extra={"error": str(e)}, exc_info=True)
        return None
