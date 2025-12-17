"""
Gemini LLM Provider Implementation
Stateless wrapper for Google Gemini API interactions via Vertex AI
"""

from google import genai
from google.genai import types
from common.logging import get_logger
import time
import json
import math

logger = get_logger(__name__)


class GeminiProvider:
    """
    Stateless Gemini provider.
    All state is passed in, client is reused.
    """

    def __init__(self, client: genai.Client):
        """
        Initialize with an existing Gemini client.

        Args:
            client: Pre-initialized genai.Client instance
        """
        self.client = client
        self.log_prob = 1
        logger.debug("GeminiProvider initialized with client")

    # ==================== Helper Methods ====================

    def content_builder(self, parts: list) -> list:
        """Build content structure for Gemini API."""
        contents = [types.Content(role="user", parts=parts)]
        return contents

    def count_tokens(self, part, model: str) -> int:
        """Count tokens for a given part and model."""
        try:
            contents = self.content_builder([part])
            count_response = self.client.models.count_tokens(model=model, contents=contents)
            return count_response.total_tokens
        except Exception as e:
            logger.error(f"Error extracting token counts: {e}")
            return 0

    def get_postcall_tokens(self, response) -> tuple:
        """Extract output and thought tokens from response."""
        try:
            thought_tokens = 0
            if response.usage_metadata.thoughts_token_count:
                thought_tokens = response.usage_metadata.thoughts_token_count

            output_tokens = response.usage_metadata.candidates_token_count
            return output_tokens, thought_tokens
        except Exception as e:
            logger.error(f"Error extracting postcall token counts: {e}")
            return 0, 0

    def get_avg_logprob(self, response) -> float:
        """Extract average log probability from response."""
        if not (response.candidates and response.candidates[0].logprobs_result):
            logger.warning("No logprobs result found in response")
            return 0

        try:
            average_logprob = response.candidates[0].avg_logprobs
            return average_logprob
        except Exception as e:
            logger.error(f"Error calculating average log probability: {e}")
            return 0

    def get_confidence_score(self, avg_logprob: float) -> float:
        """Calculate confidence score from log probability."""
        if avg_logprob is None:
            return None
        try:
            return math.exp(avg_logprob)
        except (TypeError, ValueError) as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0

    def config_builder(
        self,
        temperature: float,
        top_p: float,
        token_limit: int,
        si_text: str,
        response_schema=None,
    ):
        """Build Gemini generation config."""
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ]

        config_params = {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": token_limit,
            "response_modalities": ["TEXT"],
            "safety_settings": safety_settings,
            "system_instruction": [types.Part.from_text(text=si_text)],
        }

        if response_schema:
            config_params["response_schema"] = response_schema
            config_params["response_mime_type"] = "application/json"

        if self.log_prob > 0:
            config_params["response_logprobs"] = True
            config_params["logprobs"] = self.log_prob

        generate_content_config = types.GenerateContentConfig(**config_params)
        return generate_content_config

    def calculate_metrics(
        self, input_part, prompt_part, elapsed_time, response, model: str
    ) -> dict:
        """Calculate comprehensive metrics for the LLM call."""
        token_count_error = None

        if input_part is None:
            input_tokens = 0
        else:
            input_tokens = self.count_tokens(input_part, model)

        prompt_tokens = self.count_tokens(prompt_part, model)
        output_tokens, thought_tokens = self.get_postcall_tokens(response)

        if input_tokens is None or prompt_tokens is None:
            token_count_error = "Error calculating input or prompt tokens."
            input_tokens = input_tokens or 0
            prompt_tokens = prompt_tokens or 0
        if output_tokens is None:
            token_count_error = "Error calculating output tokens."
            output_tokens = 0
        if thought_tokens is None:
            token_count_error = "Error calculating thought tokens."
            thought_tokens = 0

        avg_logprob = self.get_avg_logprob(response)
        confidence_score = self.get_confidence_score(avg_logprob)

        metrics = {
            "input_tokens": input_tokens,
            "prompt_tokens": prompt_tokens,
            "total_input_tokens": input_tokens + prompt_tokens,
            "output_tokens": output_tokens,
            "thought_tokens": thought_tokens,
            "confidence_score": confidence_score,
            "elapsed_time": elapsed_time,
            "token_count_error": token_count_error,
        }
        return metrics

    # ==================== Main Process Method ====================

    def process(self, input_data: dict, temperature: float = 0.2, top_p: float = 0.8) -> tuple:
        """
        Process a single LLM request (stateless).

        Args:
            input_data: Dict with model, prompt, system_instruction, etc.
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter

        Returns:
            Tuple of (response_json, metrics)
        """
        model = input_data.get("model")
        token_limit = input_data.get("token_limit")
        prompt = input_data.get("prompt", None)
        system_instruction = input_data.get("system_instruction")
        response_schema = input_data.get("response_schema")

        input_type = input_data.get("input_type", None)

        if model is None or prompt is None or token_limit is None or system_instruction is None:
            logger.warning("Cannot process llm request, missing required fields")
            logger.warning(model)
            logger.warning(prompt)
            logger.warning(token_limit)
            logger.warning(system_instruction)
            logger.warning(response_schema)
            logger.warning(input_type)
            raise ValueError("Missing required fields")

        content_part = None

        # Build content part based on input type
        if input_type == "audio/wav":
            audio_bytes = input_data.get("user_data", None)
            content_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=input_type,
            )
        elif input_type == "text/plain":
            text_bytes = input_data.get("user_data", None)
            content_part = types.Part.from_text(text=text_bytes)

        # Build parts list
        parts = [types.Part.from_text(text=prompt)]
        if content_part is not None:
            parts.append(content_part)

        contents = [types.Content(role="user", parts=parts)]

        # Build config
        config = self.config_builder(
            temperature, top_p, token_limit, system_instruction, response_schema
        )

        # Make API call
        start_time = time.time()
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return None, {}

        end_time = time.time()

        if response is None or response.text is None:
            return None, {}

        # Calculate metrics
        prompt_with_si = system_instruction + "\n" + prompt
        prompt_part = types.Part.from_text(text=prompt_with_si)

        metrics = self.calculate_metrics(
            content_part, prompt_part, end_time - start_time, response, model
        )

        try:
            response_json = json.loads(response.text)
        except json.JSONDecodeError:
            response_json = {"text": response.text}

        return response_json, metrics
