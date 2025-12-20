"""
Stateless LLM call handler for processing requests through GeminiProvider.
Handles response validation and centralized error management for all LLM interactions.
"""

from common.logging import get_logger

logger = get_logger(__name__)


def call_llm(provider, input_data: dict, call_name: str):
    """
    Stateless wrapper for executing LLM processing with response tracking.

    Args:
        provider (GeminiProvider): Stateless provider instance to use.
        input_data (dict): Request parameters (model, prompt, etc.).
        call_name (str): Identifier for the call context (e.g., 'STT', 'SMART').

    Returns:
        tuple: (response_payload, metrics_dict) or (None, None) on validation or execution failure.
    """
    if provider is None:
        logger.error("Provider instance is missing", extra={"call_name": call_name})
        return None, None

    if input_data is None or not isinstance(input_data, dict):
        logger.warning("Invalid input data format", extra={"call_name": call_name})
        return None, None

    model = input_data.get("model", "unknown")
    logger.debug("Executing LLM call", extra={"call_name": call_name, "model": model})

    try:
        response, metrics = provider.process(input_data)

        if response is None:
            logger.warning("LLM returned null response", extra={"call_name": call_name})
            return None, metrics

        if metrics is None:
            logger.warning("Metrics missing for LLM call", extra={"call_name": call_name})
            metrics = {}

        if isinstance(response, dict):
            logger.debug(
                "LLM response details",
                extra={"call_name": call_name, "response_keys": list(response.keys())},
            )
        else:
            logger.warning(
                "Unexpected response format",
                extra={"call_name": call_name, "type": type(response).__name__},
            )

        return response, metrics

    except ValueError as e:
        logger.error(
            "Validation error in LLM call",
            extra={"call_name": call_name, "error": str(e)},
            exc_info=True,
        )
        return None, None
    except Exception as e:
        logger.critical(
            "Critical error in LLM call",
            extra={"call_name": call_name, "error": str(e)},
            exc_info=True,
        )
        return None, None
