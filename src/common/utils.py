"""
Shared utility functions for file I/O and Google Cloud Storage interactions.
Provides standardized methods for reading/writing files and fetching cloud assets.
"""

import json
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import storage
from common.logging import get_logger
from config.settings import GCS_SERVICE_ACCOUNT_PATH

logger = get_logger(__name__)


def get_file_type(file_path: str) -> str:
    """
    Determine the MIME type of a file based on its extension.

    Args:
        file_path (str): Path of the file to check.

    Returns:
        str: MIME type string.
    """
    extension_to_type = {
        ".txt": "text/plain",
        ".json": "application/json",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
    }
    ext = Path(file_path).suffix.lower()
    return extension_to_type.get(ext, "application/octet-stream")


def read_file(file_path: str, is_json: bool = False, is_audio: bool = False):
    """
    Read content from a local file with support for text, JSON, and binary audio.

    Args:
        file_path (str): Path to the file.
        is_json (bool): If True, parse as JSON.
        is_audio (bool): If True, read as raw bytes.

    Returns:
        any: File content (str, dict, or bytes) or None on failure.
    """
    try:
        if is_json:
            with open(file_path, "r") as f:
                return json.load(f)
        elif is_audio:
            with open(file_path, "rb") as f:
                return f.read()
        else:
            with open(file_path, "r") as f:
                return f.read()

    except FileNotFoundError:
        logger.warning("File not found", extra={"path": file_path})
        return None
    except Exception as e:
        logger.error("Failed to read file", extra={"path": file_path, "error": str(e)})
        return None


def write_file(file_path: str, content: str) -> bool:
    """
    Write text content to a local file.

    Args:
        file_path (str): Destination file path.
        content (str): Text content to write.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error("Failed to write to file", extra={"path": file_path, "error": str(e)})
        return False


def get_input_data(gcs_audio_url: str) -> bytes:
    """
    Fetch raw bytes from a Google Cloud Storage URL.

    Args:
        gcs_audio_url (str): GCS URL (gs://bucket/blob).

    Returns:
        bytes: Raw file content or None on failure.
    """
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GCS_SERVICE_ACCOUNT_PATH
        )
        client = storage.Client(credentials=credentials)
        bucket_name, blob_name = gcs_audio_url.replace("gs://", "").split("/", 1)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        audio_data = blob.download_as_bytes()
        logger.debug(
            "Fetched bytes from GCS", extra={"url": gcs_audio_url, "size_bytes": len(audio_data)}
        )
        return audio_data
    except Exception as e:
        logger.error("Failed to fetch from GCS", extra={"url": gcs_audio_url, "error": str(e)})
        return None
