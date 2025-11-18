
from fastapi import FastAPI
from utility.logging import get_logger,configure_logging


app = FastAPI()
logger = get_logger(__name__)

@app.get("/health")
def health():
    logger.info("Health check endpoint called")
    return {"status": "ok"}


