"""
Utility functions for external service communications.
Primarily handles data transmission to upstream systems via HTTP.
"""

import requests
from common.logging import get_logger
from config.settings import UPSTREAM_URL as API_URL

logger = get_logger(__name__)


def upstream_call(upstream_output: dict):
    """
    Transmit processed pipeline output to the upstream API.

    Args:
        upstream_output (dict): The complete payload to send upstream.
    """
    logger.debug("Transmitting output to upstream", extra={"data": upstream_output})
    try:
        response = requests.post(f"{API_URL}/processed-output", json=upstream_output)
        response.raise_for_status()
        logger.debug("Upstream transmission successful", extra={"response": response.text})
    except requests.exceptions.HTTPError as e:
        error_message = e.response.json().get("error", "Unknown API error")
        logger.error("Upstream HTTP error", extra={"error": error_message})
    except requests.exceptions.RequestException as e:
        logger.critical("Upstream request failed", extra={"error": str(e)})
