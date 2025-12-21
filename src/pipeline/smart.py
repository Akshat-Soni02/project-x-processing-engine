"""
SMART Pipeline implementation.
Processes input to generate context and final notes using Vector DB and LLMs.
"""

from typing import Any, Dict, Optional, Tuple
from config.config import Llm_Call, User_Input_Type, Pipeline as PipelineEnum
from db.db import Database
from impl.context_utils import format_sentences, prepare_context_for_noteback
from impl.gemini import GeminiProvider
from impl.llm_input import get_llm_input
from impl.llm_processor import call_llm
from pipeline.base import Pipeline
from pipeline.exceptions import FatalPipelineError


class SmartPipeline(Pipeline):
    """
    Pipeline for SMART processing (Context Extraction + Noteback Generation).
    """

    def __init__(
        self,
        smart_provider: GeminiProvider,
        noteback_provider: GeminiProvider,
        vector_db: Database,
    ):
        super().__init__(PipelineEnum.SMART.value)
        self.smart_provider = smart_provider
        self.noteback_provider = noteback_provider
        self.vector_db = vector_db

    def _process(
        self, input_data: Any, context: Dict[str, Any]
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Execute SMART logic.

        Args:
            input_data (Any): Raw input.
            context (Dict[str, Any]): Metadata.

        Returns:
            Tuple[Optional[Dict], Optional[Dict]]: Response and metrics.
        """
        input_type = context.get("input_type", User_Input_Type.AUDIO_WAV)

        if not input_data:
            raise FatalPipelineError("Empty or null input provided")

        # 1. Prepare Input for Context Call
        try:
            smart_input_data = get_llm_input(Llm_Call.SMART, input_data, input_type)
        except Exception as e:
            raise FatalPipelineError("Failed to prepare input data", original_error=e)

        if smart_input_data is None:
            raise FatalPipelineError("Input data preparation returned null")

        # 2. Call LLM for Context
        try:
            context_response, _ = call_llm(self.smart_provider, smart_input_data, Llm_Call.SMART)
        except Exception as e:
            raise FatalPipelineError("Context preparation call failed", original_error=e)

        if context_response is None:
            self.logger.warning("Context preparation returned null")
            return None, None

        if not isinstance(context_response, dict):
            raise FatalPipelineError(
                f"Invalid context response type: {type(context_response).__name__}"
            )

        # 3. Prepare Vector DB Context
        try:
            similarity_context = prepare_context_for_noteback(context_response, self.vector_db)
        except Exception as e:
            # This was logged as error in original code, treating as fatal for pipeline integrity
            raise FatalPipelineError("Failed to prepare similarity context", original_error=e)

        try:
            formatted_sentences = format_sentences(context_response)
        except Exception as e:
            raise FatalPipelineError("Failed to format sentences", original_error=e)

        # 4. Prepare Input for Noteback Call
        try:
            formatted_sentences_str = "\n".join(formatted_sentences) if formatted_sentences else ""
            similarity_context_str = "\n".join(similarity_context) if similarity_context else ""

            if not formatted_sentences_str:
                self.logger.warning("No formatted sentences available")
            if not similarity_context_str:
                self.logger.warning("No similarity context available")

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

            noteback_input_data = get_llm_input(Llm_Call.NOTEBACK, input_data, input_type, replace)
            if noteback_input_data is None:
                raise FatalPipelineError("Failed to prepare noteback input data")

        except Exception as e:
            raise FatalPipelineError("Failed to prepare noteback input", original_error=e)

        # 5. Call LLM for Noteback
        try:
            noteback_response, noteback_metrics = call_llm(
                self.noteback_provider, noteback_input_data, Llm_Call.NOTEBACK
            )
        except Exception as e:
            raise FatalPipelineError("Noteback LLM call failed", original_error=e)

        if noteback_response is None:
            self.logger.warning("Noteback processing returned null response")
            return None, None

        return noteback_response, noteback_metrics
