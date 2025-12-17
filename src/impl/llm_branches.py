from impl.gemini import GeminiProvider
from impl.llm_processor import call_llm
from impl.context_utils import prepare_context_for_noteback, format_sentences
from common.logging import get_logger

from config.config import Llm_Call, User_Input_Type
from impl.llm_input import get_llm_input
from vector.db import Database

logger = get_logger(__name__)


def stt_branch(stt_provider: GeminiProvider, input: bytes, input_type: User_Input_Type):
    """STT branch: Processes audio input through speech-to-text pipeline."""
    logger.info("[STT BRANCH] Starting STT processing...")

    try:
        # Validate input
        if input is None or len(input) == 0:
            logger.error("[STT BRANCH] Invalid input - empty or None")
            return None, None

        # Prepare input data
        try:
            stt_input_data = get_llm_input(Llm_Call.STT, input, input_type)
        except Exception as e:
            logger.error(f"[STT BRANCH] Failed to prepare input data: {str(e)}", exc_info=True)
            return None, None

        if stt_input_data is None:
            logger.error("[STT BRANCH] STT input data preparation returned None")
            return None, None

        logger.debug("STT input data prepared")

        try:
            response, metrics = call_llm(stt_provider, stt_input_data, Llm_Call.STT)
        except Exception as e:
            logger.error(f"[STT BRANCH] LLM call failed: {str(e)}", exc_info=True)
            return None, None

        if response is None:
            logger.error("[STT BRANCH] STT processing returned empty response")
            return None, None

        if not isinstance(response, dict):
            logger.warning(f"[STT BRANCH] Unexpected response type: {type(response).__name__}")

        logger.info("[STT BRANCH] STT processing completed successfully")
        logger.debug(
            f"STT Response keys: {response.keys() if isinstance(response, dict) else 'N/A'}"
        )
        return response, metrics
    except Exception as e:
        logger.error(f"[STT BRANCH] Unhandled exception: {str(e)}", exc_info=True)
        return None, None


def smart_branch(
    smart_provider: GeminiProvider,
    noteback_provider: GeminiProvider,
    vector_db: Database,
    input: bytes,
    input_type: User_Input_Type,
):
    """Smart branch: Processes text through context preparation and noteback pipeline."""
    logger.info("[SMART BRANCH] Starting smart branch processing...")

    try:
        # Validate input
        if input is None or len(input) == 0:
            logger.error("[SMART BRANCH] Invalid input - empty or None")
            return None, None

        logger.debug("[SMART BRANCH] Step 1/4: Preparing input data...")
        try:
            smart_input_data = get_llm_input(Llm_Call.SMART, input, input_type)
        except Exception as e:
            logger.error(f"[SMART BRANCH] Failed to prepare input data: {str(e)}", exc_info=True)
            return None, None

        if smart_input_data is None:
            logger.error("[SMART BRANCH] Smart input data preparation returned None")
            return None, None
        logger.debug("Smart input data loaded")

        logger.debug("[SMART BRANCH] Step 2/4: Executing context preparation LLM call...")
        try:
            context_response, context_metrics = call_llm(
                smart_provider, smart_input_data, Llm_Call.SMART
            )
        except Exception as e:
            logger.error(
                f"[SMART BRANCH] Context preparation LLM call failed: {str(e)}", exc_info=True
            )
            return None, None

        if context_response is None:
            logger.error("[SMART BRANCH] Context preparation failed - aborting")
            return None, None

        if not isinstance(context_response, dict):
            logger.error(
                f"[SMART BRANCH] Invalid context response type: {type(context_response).__name__}"
            )
            return None, None

        logger.debug("[SMART BRANCH] Context preparation completed")
        logger.debug(f"Context response keys: {list(context_response.keys())}")

        # Prepare vector database context
        logger.debug("[SMART BRANCH] Step 3/4: Preparing noteback context from vector DB...")

        try:
            # Get similarity context
            similarity_context = prepare_context_for_noteback(context_response, vector_db)
            logger.info(f"Prepared {len(similarity_context)} similarity context items")
            logger.debug(
                f"Similarity sample: {similarity_context[0] if similarity_context else 'Empty'}"
            )
        except Exception as e:
            logger.error(
                f"[SMART BRANCH] Failed to prepare similarity context: {str(e)}", exc_info=True
            )
            return None, None

        try:
            formatted_sentences = format_sentences(context_response)
            logger.info(f"Formatted {len(formatted_sentences)} sentences for noteback context")
            logger.debug(
                f"Sentence sample: {formatted_sentences[0] if formatted_sentences else 'Empty'}"
            )
        except Exception as e:
            logger.error(f"[SMART BRANCH] Failed to format sentences: {str(e)}", exc_info=True)
            return None, None

        # Execute noteback LLM call with prepared context
        logger.debug("[SMART BRANCH] Step 4/4: Executing noteback LLM call...")

        try:
            formatted_sentences_str = "\n".join(formatted_sentences) if formatted_sentences else ""
            similarity_context_str = "\n".join(similarity_context) if similarity_context else ""

            if not formatted_sentences_str:
                logger.warning("[SMART BRANCH] No formatted sentences available")
            if not similarity_context_str:
                logger.warning("[SMART BRANCH] No similarity context available")

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
                logger.error("[SMART BRANCH] Failed to prepare noteback input data")
                return None, None

        except Exception as e:
            logger.error(
                f"[SMART BRANCH] Failed to prepare noteback input: {str(e)}", exc_info=True
            )
            return None, None

        try:
            noteback_response, noteback_metrics = call_llm(
                noteback_provider, noteback_input_data, Llm_Call.NOTEBACK
            )
        except Exception as e:
            logger.error(f"[SMART BRANCH] Noteback LLM call failed: {str(e)}", exc_info=True)
            return None, None

        if noteback_response is None:
            logger.error("[SMART BRANCH] Noteback processing returned empty response")
            return None, None

        logger.info("[SMART BRANCH] Smart branch pipeline completed successfully")
        logger.debug(
            f"Noteback response keys: {noteback_response.keys() if isinstance(noteback_response, dict) else 'N/A'}"
        )

        return noteback_response, noteback_metrics
    except Exception as e:
        logger.error(f"[SMART BRANCH] Unhandled exception: {str(e)}", exc_info=True)
        return None, None
