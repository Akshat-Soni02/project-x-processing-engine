import json
from pathlib import Path
from common.logging import get_logger
from google.oauth2 import service_account
from config.settings import GCS_SERVICE_ACCOUNT_PATH
from google.cloud import storage
logger = get_logger(__name__)


def get_file_type(file_path: str) -> str:
    """Determine the MIME type of a file based on its extension."""
    extension_to_type = {
        ".txt": "text/plain",
        ".json": "application/json",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
    }
    ext = Path(file_path).suffix.lower()
    return extension_to_type.get(ext, "application/octet-stream")


def read_file(file_path, is_json=False, is_audio=False):
    """
    Read and return text content from a file.

    Args:
        file_path (str): Path to the file to read.

    Returns:
        str or None: File content as a string, or None if the file is missing or an error occurs.
    """
    try:
        if is_json:
            with open(file_path, "r") as f:
                content = json.load(f)
            return content
        elif is_audio:
            with open(file_path, "rb") as f:
                content = f.read()
            return content
        else:
            with open(file_path, "r") as f:
                content = f.read()
            return content

    except FileNotFoundError:
        logger.error(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None


def write_file(file_path, content):
    """
    Write text content to a file.

    Args:
        file_path (str): Destination file path.
        content (str): Text content to write.

    Returns:
        bool: True if write succeeded, False otherwise.
    """
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return False


def get_input_data(gcs_audio_url: str) -> bytes:
    """
    Fetch audio data from a GCS URL.

    Args:
        gcs_audio_url (str): GCS URL of the audio file.
    Returns:
        bytes: Audio file content as bytes, or None if an error occurs.
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
        return audio_data
    except Exception as e:
        logger.error(f"Error fetching audio from {gcs_audio_url}: {e}")
        return None
