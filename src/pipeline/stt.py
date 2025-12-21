"""
STT Pipeline implementation.
Processes audio input to generate text transcriptions.
"""

from typing import Any, Dict, Optional, Tuple
from config.config import Llm_Call, User_Input_Type, Pipeline as PipelineEnum
from impl.gemini import GeminiProvider
from impl.llm_input import get_llm_input
from impl.llm_processor import call_llm
from pipeline.base import Pipeline
from pipeline.exceptions import FatalPipelineError


class SttPipeline(Pipeline):
    """
    Pipeline for Speech-to-Text processing.
    """

    def __init__(self, stt_provider: GeminiProvider):
        super().__init__(PipelineEnum.STT.value)
        self.stt_provider = stt_provider

    def _process(
        self, input_data: Any, context: Dict[str, Any]
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Execute STT logic.

        Args:
            input_data (Any): Raw input (audio bytes).
            context (Dict[str, Any]): Metadata.

        Returns:
            Tuple[Optional[Dict], Optional[Dict]]: Response and metrics.
        """
        input_type = context.get("input_type", User_Input_Type.AUDIO_WAV)

        if not input_data:
            raise FatalPipelineError("Empty or null input provided")

        try:
            stt_input_data = get_llm_input(Llm_Call.STT, input_data, input_type)
        except Exception as e:
            raise FatalPipelineError("Failed to prepare input data", original_error=e)

        if stt_input_data is None:
            raise FatalPipelineError("Input data preparation returned null")

        try:
            response, metrics = call_llm(self.stt_provider, stt_input_data, Llm_Call.STT)
        except Exception as e:
            # Assuming LLM call failures might be transient or fatal depending on the error,
            # but for now mapping to Fatal to stop execution as per original logic's critical log.
            # In a real scenario, we'd check for specific transient errors (e.g. 503).
            raise FatalPipelineError("LLM call failed", original_error=e)

        if response is None:
            self.logger.warning("Processing returned empty response")
            return None, None

        if not isinstance(response, dict):
            self.logger.warning("Unexpected response type", extra={"type": type(response).__name__})

        return response, metrics
