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
        Tuple of (response, metrics)
    """
    model = input_data.get("model", "unknown")
    logger.debug(f"[{call_name}] Calling Gemini with model: {model}")

    try:
        response, metrics = provider.process(input_data)
        logger.debug(f"[{call_name}] LLM processing completed")

        if response is None:
            logger.error(f"[{call_name}] LLM returned None response")
            return None, metrics

        if isinstance(response, dict):
            logger.debug(f"[{call_name}] Response keys: {list(response.keys())}")

        logger.debug(f"✓ [{call_name}] LLM call completed successfully")
        return response, metrics

    except Exception as e:
        logger.error(f"✗ [{call_name}] LLM call failed: {str(e)}", exc_info=True)
        raise
