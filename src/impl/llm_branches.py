"""
Implementation of specific LLM processing branches.
Orchestrates data preparation, LLM calls, and context management for STT and SMART pipelines.
"""

from impl.gemini import GeminiProvider
from impl.llm_processor import call_llm
from impl.context_utils import prepare_context_for_noteback, format_sentences
from common.logging import get_logger

from config.config import Llm_Call, User_Input_Type
from impl.llm_input import get_llm_input
from vector.db import Database

logger = get_logger(__name__)


def stt_branch(stt_provider: GeminiProvider, input: bytes, input_type: User_Input_Type):
    """
    Process audio input through the speech-to-text pipeline.

    Args:
        stt_provider (GeminiProvider): Provider instance for STT.
        input (bytes): Raw audio data.
        input_type (User_Input_Type): MIME type of the input.

    Returns:
        tuple: (response_dict, metrics_dict) or (None, None) on error.
    """
    try:
        if input is None or len(input) == 0:
            logger.warning("Empty or null input provided")
            return None, None

        try:
            stt_input_data = get_llm_input(Llm_Call.STT, input, input_type)
        except Exception as e:
            logger.error("Failed to prepare input data", extra={"error": str(e)}, exc_info=True)
            return None, None

        if stt_input_data is None:
            logger.warning("Input data preparation returned null")
            return None, None

        try:
            response, metrics = call_llm(stt_provider, stt_input_data, Llm_Call.STT)
        except Exception as e:
            logger.critical("LLM call failed", extra={"error": str(e)}, exc_info=True)
            return None, None

        if response is None:
            logger.warning("Processing returned empty response")
            return None, None

        if not isinstance(response, dict):
            logger.warning("Unexpected response type", extra={"type": type(response).__name__})

        return response, metrics
    except Exception as e:
        logger.critical("Unhandled exception in processing", extra={"error": str(e)}, exc_info=True)
        return None, None


def smart_branch(
    smart_provider: GeminiProvider,
    noteback_provider: GeminiProvider,
    vector_db: Database,
    input: bytes,
    input_type: User_Input_Type,
):
    """
    Process text through context preparation and noteback pipeline.

    Args:
        smart_provider (GeminiProvider): Provider for context extraction.
        noteback_provider (GeminiProvider): Provider for final noteback generation.
        vector_db (Database): Database instance for similarity search.
        input (bytes): Raw input data.
        input_type (User_Input_Type): MIME type of the input.

    Returns:
        tuple: (response_dict, metrics_dict) or (None, None) on error.
    """
    try:
        if input is None or len(input) == 0:
            logger.warning("Empty or null input provided")
            return None, None

        try:
            smart_input_data = get_llm_input(Llm_Call.SMART, input, input_type)
        except Exception as e:
            logger.error("Failed to prepare input data", extra={"error": str(e)}, exc_info=True)
            return None, None

        if smart_input_data is None:
            logger.warning("Input data preparation returned null")
            return None, None

        try:
            context_response, context_metrics = call_llm(
                smart_provider, smart_input_data, Llm_Call.SMART
            )
        except Exception as e:
            logger.critical(
                "Context preparation call failed", extra={"error": str(e)}, exc_info=True
            )
            return None, None

        if context_response is None:
            logger.warning("Context preparation returned null")
            return None, None

        if not isinstance(context_response, dict):
            logger.error(
                "Invalid context response type", extra={"type": type(context_response).__name__}
            )
            return None, None

        # Prepare vector database context
        try:
            similarity_context = prepare_context_for_noteback(context_response, vector_db)
        except Exception as e:
            logger.error(
                "Failed to prepare similarity context", extra={"error": str(e)}, exc_info=True
            )
            return None, None

        try:
            formatted_sentences = format_sentences(context_response)
        except Exception as e:
            logger.error("Failed to format sentences", extra={"error": str(e)}, exc_info=True)
            return None, None

        # Execute noteback LLM call with prepared context
        try:
            formatted_sentences_str = "\n".join(formatted_sentences) if formatted_sentences else ""
            similarity_context_str = "\n".join(similarity_context) if similarity_context else ""

            if not formatted_sentences_str:
                logger.warning("No formatted sentences available")
            if not similarity_context_str:
                logger.warning("No similarity context available")

            replace = [
                {
                    "type": "prompt",
                    "replace_key": "{{current_note}}",
                    "replace_value": formatted_sentences_str,
                },
                {
                    "type": "prompt",
                    "replace_key": "{{history_context}}",
                    "replace_value": similarity_context_str,
                },
            ]

            noteback_input_data = get_llm_input(Llm_Call.NOTEBACK, input, input_type, replace)
            if noteback_input_data is None:
                logger.warning("Failed to prepare noteback input data")
                return None, None

        except Exception as e:
            logger.error("Failed to prepare noteback input", extra={"error": str(e)}, exc_info=True)
            return None, None

        try:
            noteback_response, noteback_metrics = call_llm(
                noteback_provider, noteback_input_data, Llm_Call.NOTEBACK
            )
        except Exception as e:
            logger.critical("Noteback LLM call failed", extra={"error": str(e)}, exc_info=True)
            return None, None

        if noteback_response is None:
            logger.warning("Noteback processing returned null response")
            return None, None

        return noteback_response, noteback_metrics
    except Exception as e:
        logger.critical("Unhandled exception in processing", extra={"error": str(e)}, exc_info=True)
        return None, None
