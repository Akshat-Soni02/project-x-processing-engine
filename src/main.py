from fastapi import FastAPI
from common.logging import get_logger
from common.utils import read_file
from google import genai

import os
from pathlib import Path

from impl.llm_branches import stt_branch, smart_branch
from impl.gemini import GeminiProvider
from config import Project, User_Input_Type
from vector.db import Database

app = FastAPI()
logger = get_logger(__name__)

# ==================== LLM Client Initialization ====================
# Initialize Gemini clients at startup for reuse
# Each provider gets its own client instance for independent scaling
project_root = Path(__file__).parent.parent
cred_path = project_root / "credentials.json"
if cred_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    logger.info("Set GOOGLE_APPLICATION_CREDENTIALS from local file.")
else:
    logger.warning(
        "credentials.json not found; relying on Application Default Credentials or gcloud config."
    )


print(Project.PROJECT_ID)

# vertexai.init(project=Project.PROJECT_ID, location=Project.LOCATION)

gemini_client = genai.Client(
    vertexai=Project.ENABLE_VERTEX_AI, project=Project.PROJECT_ID, location=Project.LOCATION
)
logger.info("Initialized Vertex AI Gemini Client")

# Create stateless provider instances (reuse same client)
stt_provider = GeminiProvider(gemini_client)
smart_provider = GeminiProvider(gemini_client)
noteback_provider = GeminiProvider(gemini_client)

logger.info("Initialized STT, Smart, and Noteback providers")

vector_db = Database()
logger.info("Initialized Vector Database")

# Load input file with error handling
input_data = None
try:
    input_data = read_file("test.wav", is_audio=True)
    if input_data is None:
        logger.warning("Input file loaded but is empty")
    else:
        logger.info(f"Successfully loaded input file ({len(input_data)} bytes)")
except FileNotFoundError:
    logger.error("Input file 'test.wav' not found")
except Exception as e:
    logger.error(f"Failed to load input file: {str(e)}", exc_info=True)


# ==================== Request Handlers ====================
# these runs will be based on pubsub topics but for testing we are doing through functions

# input should be audio bytes
# we will not save new sentences to vector from here, instead we just return and the output and let java server handle this


def run_stt():
    if input_data is None:
        logger.error("[STT] Cannot run - input data not available")
        return None

    try:
        response, metrics = stt_branch(stt_provider, input_data, User_Input_Type.AUDIO_WAV)
        logger.info("[STT] Response received successfully")
        return response
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
        return response
    except Exception as e:
        logger.error(f"[SMART] Pipeline failed: {str(e)}", exc_info=True)
        return None


# Server health check endpoint
@app.get("/health")
def health():
    logger.info("Health check working")
    return {"status": "ok"}


# run_stt()
# run_smart()

# Testing endpoints


# TOREMOVE
# Add support to take audios as input  done
# log audio format & audio properties  already
# log data came after processing audio - processing time,
# processed audio time, processed audio format [if changed]
# Appropriate errors when - failed to find lib, failed to process due to upstream, failure due to server issues, warnings when taking longer then expected time [comparison against predetermined time with ref to some metric]
# @app.post("/augment-audio")
# async def augment_audio(audio_file: Annotated[UploadFile, File()]):
#     audio_bytes = await audio_file.read()

#     service = AudioAugmentation({})
#     audio = service.run_pipeline(audio_bytes)

#     with open("output_audio.wav", "wb") as f:
#         f.write(audio)
#     return {"message": "Audio augmentation endpoint"}


# @app.post("/llm-test")
# def llm_test():
#     from services.llm_service import LLMService

#     config = {
#         "provider": "gemini",
#         "api_key": "AQ.Ab8RN6LbX-AmjvGNCW_E0Q7gi30mD7atLhLcGCHEKJbHQniZbw",
#         "model_name": "gemini-2.5-flash",
#         "temperature": 0.5,
#         "max_tokens": 150,
#     }

#     config = ConfigDict(**config)
#     llm_service = LLMService(config)
#     response = llm_service.process("Hello, how are you?")
#     return {"llm_response": response.content}
