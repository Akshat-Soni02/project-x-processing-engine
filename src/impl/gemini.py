"""
Gemini LLM Provider Implementation.
Stateless wrapper for Google Gemini API interactions via Vertex AI.
"""

import time
import json
import math
from google import genai
from google.genai import types
from common.logging import get_logger

logger = get_logger(__name__)


class GeminiProvider:
    """
    Stateless Gemini provider for handling LLM interactions.
    Maintains no conversation state; all context is passed per-request.
    """

    def __init__(self, client: genai.Client):
        """
        Initialize the provider with an existing Gemini client.

        Args:
            client (genai.Client): Pre-initialized Google GenAI client instance.
        """
        self.client = client
        self.log_prob = 1
        logger.debug("Provider initialized")

    def content_builder(self, parts: list) -> list:
        """
        Build the content structure for Gemini API calls.

        Args:
            parts (list): List of content parts (text, bytes, etc.).

        Returns:
            list: List containing the Content object.
        """
        contents = [types.Content(role="user", parts=parts)]
        return contents

    def count_tokens(self, part, model: str) -> int:
        """
        Calculate the token count for a specific part and model.

        Args:
            part: The content part to count.
            model (str): The model ID to use for tokenization.

        Returns:
            int: Total token count.
        """
        try:
            contents = self.content_builder([part])
            count_response = self.client.models.count_tokens(model=model, contents=contents)
            return count_response.total_tokens
        except Exception as e:
            logger.error("Failed to count tokens", extra={"error": str(e)})
            return 0

    def get_postcall_tokens(self, response) -> tuple:
        """
        Extract usage metrics from the API response.

        Args:
            response: The Gemini API response object.

        Returns:
            tuple: (output_tokens, thought_tokens)
        """
        try:
            thought_tokens = 0
            if response.usage_metadata.thoughts_token_count:
                thought_tokens = response.usage_metadata.thoughts_token_count

            output_tokens = response.usage_metadata.candidates_token_count
            return output_tokens, thought_tokens
        except Exception as e:
            logger.error("Failed to extract post-call tokens", extra={"error": str(e)})
            return 0, 0

    def get_avg_logprob(self, response) -> float:
        """
        Extract the average log probability from the API response.

        Args:
            response: The Gemini API response object.

        Returns:
            float: Average log probability value.
        """
        if not (response.candidates and response.candidates[0].logprobs_result):
            logger.warning("Logprobs result missing in response")
            return 0

        try:
            average_logprob = response.candidates[0].avg_logprobs
            return average_logprob
        except Exception as e:
            logger.error("Failed to calculate average log probability", extra={"error": str(e)})
            return 0

    def get_confidence_score(self, avg_logprob: float) -> float:
        """
        Convert log probability to a 0-1 confidence score.

        Args:
            avg_logprob (float): Average log probability.

        Returns:
            float: Exponentially mapped confidence score.
        """
        if avg_logprob is None:
            return None
        try:
            return math.exp(avg_logprob)
        except (TypeError, ValueError) as e:
            logger.error("Failed to calculate confidence score", extra={"error": str(e)})
            return 0

    def config_builder(
        self,
        temperature: float,
        top_p: float,
        token_limit: int,
        si_text: str,
        response_schema=None,
    ):
        """
        Construct the generation configuration for Gemini.

        Args:
            temperature (float): Sampling temperature.
            top_p (float): Nucleus sampling parameter.
            token_limit (int): Maximum output tokens.
            si_text (str): System instruction text.
            response_schema (dict, optional): JSON schema for structured output.

        Returns:
            types.GenerateContentConfig: Fully constructed config object.
        """
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

        return types.GenerateContentConfig(**config_params)

    def calculate_metrics(
        self, input_part, prompt_part, elapsed_time, response, model: str
    ) -> dict:
        """
        Calculate execution metrics including token counts and confidence scores.

        Args:
            input_part: The raw input part (audio/text).
            prompt_part: The formatted prompt part.
            elapsed_time (float): Time taken for the API call in seconds.
            response: Gemini response object.
            model (str): Model name used.

        Returns:
            dict: Comprehensive metrics dictionary.
        """
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

    def process(self, input_data: dict, temperature: float = 0.2, top_p: float = 0.8) -> tuple:
        """
        Process a single LLM request statelessly.

        Args:
            input_data (dict): Dictionary containing model, prompt, system_instruction, etc.
            temperature (float, optional): Sampling temperature. Defaults to 0.2.
            top_p (float, optional): Nucleus sampling. Defaults to 0.8.

        Returns:
            Tuple[dict, dict]: (response_json, metrics_dict).
        """
        model = input_data.get("model")
        token_limit = input_data.get("token_limit")
        prompt = input_data.get("prompt", None)
        system_instruction = input_data.get("system_instruction")
        response_schema = input_data.get("response_schema")
        input_type = input_data.get("input_type", None)

        if model is None or prompt is None or token_limit is None or system_instruction is None:
            logger.warning(
                "Request missing required fields",
                extra={
                    "model": model,
                    "token_limit": token_limit,
                    "prompt_preview": prompt[:20] if prompt else None,
                    "si_preview": system_instruction[:20] if system_instruction else None,
                },
            )
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
            logger.critical("Gemini content generation failed", extra={"error": str(e)})
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
