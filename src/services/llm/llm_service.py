from common.logging import get_logger
from google import genai
from config.config import User_Input_Type
from config.settings import GCP_PROJECT_ID,GCP_LOCATION,ENABLE_VERTEX_AI
from impl.gemini import GeminiProvider
from impl.llm_branches import stt_branch, smart_branch
from pathlib import Path
from vector.db import Database
from common.utils import read_file




# ==================== LLM Client Initialization ====================
# Initialize Gemini clients at startup for reuse
# Each provider gets its own client instance for independent scaling


# Load input file with error handling
logger = get_logger(__name__)
vector_db = Database()

input_data = None
try:
    input_data = read_file("/Users/bhavyashah/Documents/Coding/project-x/arilo-processing-engine/test.wav", is_audio=True)
    if input_data is None:
        logger.warning("Input file loaded but is empty")
    else:
        logger.info(f"Successfully loaded input file ({len(input_data)} bytes)")
except FileNotFoundError:
    logger.error("Input file 'test.wav' not found")
except Exception as e:
    logger.error(f"Failed to load input file: {str(e)}", exc_info=True)



gemini_client = genai.Client(
    vertexai=ENABLE_VERTEX_AI, project=GCP_PROJECT_ID, location=GCP_LOCATION
)
logger.info("Initialized Vertex AI Gemini Client")


# ==================== Request Handlers ====================
# these runs will be based on pubsub topics but for testing we are doing through functions

# input should be audio bytes
# we will not save new sentences to vector from here, instead we just return and the output and let java server handle this

# Create stateless provider instances (reuse same client)
stt_provider = GeminiProvider(gemini_client)
smart_provider = GeminiProvider(gemini_client)
noteback_provider = GeminiProvider(gemini_client)



def run_stt():
    if input_data is None:
        logger.error("[STT] Cannot run - input data not available")
        return None

    try:
        response, metrics = stt_branch(stt_provider, input_data, User_Input_Type.AUDIO_WAV)
        logger.info("[STT] Response received successfully")
        return response,metrics
    except Exception as e:
        logger.error(f"[STT] Pipeline failed: {str(e)}", exc_info=True)
        return None


def run_smart():
    if input_data is None:
        logger.error("[SMART] Cannot run - input data not available")
        return None

    try:
        response, metrics = smart_branch(
            smart_provider, noteback_provider, vector_db, input_data, User_Input_Type.AUDIO_WAV
        )
        logger.info("[SMART] Response received successfully")
        return response,metrics
    except Exception as e:
        logger.error(f"[SMART] Pipeline failed: {str(e)}", exc_info=True)
        return None
