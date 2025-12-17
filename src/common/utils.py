import json
from pathlib import Path
from common.logging import get_logger

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
