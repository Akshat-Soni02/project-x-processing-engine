"""
Stateless LLM call handler for processing requests through GeminiProvider.
Handles response persistence and error management.
"""

from common.logging import get_logger

logger = get_logger(__name__)


def call_llm(provider, input_data: dict, call_name: str):
    """
    Stateless wrapper for LLM processing with response tracking.

    Args:
        provider: GeminiProvider instance (stateless)
        input_data: Dict with model, prompt, system_instruction, etc.
        call_name: Name of this call (e.g., STT, SMART, NOTEBACK)

    Returns:
        Tuple of (response, metrics) or (None, None) on error
    """
    # Validate inputs
    if provider is None:
        logger.error(f"[{call_name}] Provider is None")
        return None, None

    if input_data is None or not isinstance(input_data, dict):
        logger.error(f"[{call_name}] Invalid input_data - must be a dict")
        return None, None

    model = input_data.get("model", "unknown")
    logger.debug(f"[{call_name}] Calling Gemini with model: {model}")

    try:
        response, metrics = provider.process(input_data)
        logger.debug(f"[{call_name}] LLM processing completed")

        if response is None:
            logger.error(f"[{call_name}] LLM returned None response")
            return None, metrics

        if metrics is None:
            logger.warning(f"[{call_name}] Metrics are None")
            metrics = {}

        if isinstance(response, dict):
            logger.debug(f"[{call_name}] Response keys: {list(response.keys())}")
        else:
            logger.warning(f"[{call_name}] Unexpected response type: {type(response).__name__}")

        logger.debug(f"✓ [{call_name}] LLM call completed successfully")
        return response, metrics

    except ValueError as e:
        logger.error(f"[{call_name}] Validation error: {str(e)}", exc_info=True)
        return None, None
    except Exception as e:
        logger.error(f"[{call_name}] LLM call failed: {str(e)}", exc_info=True)
        return None, None
