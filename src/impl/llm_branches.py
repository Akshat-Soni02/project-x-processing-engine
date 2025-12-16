from impl.gemini import GeminiProvider
from impl.llm_processor import call_llm
from impl.context_utils import prepare_context_for_noteback, format_sentences
from common.logging import get_logger

from config import Llm_Call, User_Input_Type
from impl.llm_input import get_llm_input
from vector.db import Database

logger = get_logger(__name__)


def stt_branch(stt_provider: GeminiProvider, input: bytes, input_type: User_Input_Type):
    """STT branch: Processes audio input through speech-to-text pipeline."""
    logger.info("[STT BRANCH] Starting STT processing...")

    try:
        # Prepare input data
        stt_input_data = get_llm_input(Llm_Call.STT, input, input_type)

        if stt_input_data is None:
            logger.error("[STT BRANCH] STT input data preparation failed")
            return None, None

        logger.debug("STT input data prepared")

        response, metrics = call_llm(stt_provider, stt_input_data, Llm_Call.STT)

        if response is None:
            logger.error("[STT BRANCH] STT processing returned empty response")
            return None, None

        logger.debug("[STT BRANCH] STT processing completed successfully")
        logger.debug(
            f"STT Response keys: {response.keys() if isinstance(response, dict) else 'N/A'}"
        )
        return response, metrics
    except Exception as e:
        logger.critical(f"[STT BRANCH] Fatal error in STT branch: {str(e)}", exc_info=True)
        raise


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
        logger.debug("[SMART BRANCH] Step 1/3: Preparing input data...")
        smart_input_data = get_llm_input(Llm_Call.SMART, input, input_type)
        logger.debug("Smart input data loaded")

        logger.debug("[SMART BRANCH] Step 2/3: Executing context preparation LLM call...")
        context_response, context_metrics = call_llm(
            smart_provider, smart_input_data, Llm_Call.SMART
        )

        if context_response is None:
            logger.error("[SMART BRANCH] Context preparation failed - aborting")
            return None, None

        logger.debug("[SMART BRANCH] Context preparation completed")
        logger.debug(f"Context response keys: {context_response.keys()}")

        # Prepare vector database context
        logger.debug("[SMART BRANCH] Step 3/3: Preparing noteback context from vector DB...")

        # Get similarity context
        similarity_context = prepare_context_for_noteback(context_response, vector_db)
        logger.info(f"Prepared {len(similarity_context)} similarity context items")
        logger.debug(
            f"Similarity sample: {similarity_context[0] if similarity_context else 'Empty'}"
        )

        formatted_sentences = format_sentences(context_response)
        logger.info(f"Saved {len(formatted_sentences)} new sentences to vector DB")
        logger.debug(
            f"Sentence sample: {formatted_sentences[0] if formatted_sentences else 'Empty'}"
        )

        # Execute noteback LLM call with prepared context
        logger.info("[SMART BRANCH] Step 4/4: Executing noteback LLM call...")

        replace = [
            {
                "type": "prompt",
                "replace_key": "{{current_note}}",
                "replace_value": formatted_sentences,
            },
            {
                "type": "prompt",
                "replace_key": "{{history_context}}",
                "replace_value": similarity_context,
            },
        ]

        noteback_input_data = get_llm_input(Llm_Call.NOTEBACK, input, input_type, replace)

        noteback_response, noteback_metrics = call_llm(
            noteback_provider, noteback_input_data, Llm_Call.NOTEBACK
        )

        if noteback_response is None:
            logger.error("[SMART BRANCH] Noteback processing returned empty response")
            return None, None

        logger.warning("[SMART BRANCH] Smart branch pipeline completed successfully")
        logger.debug(
            f"Noteback response keys: {noteback_response.keys() if isinstance(noteback_response, dict) else 'N/A'}"
        )

        return noteback_response, noteback_metrics
    except Exception as e:
        logger.critical(f"✗ [SMART BRANCH] Fatal error in smart branch: {str(e)}", exc_info=True)
        raise
