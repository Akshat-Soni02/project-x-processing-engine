# import os
# import time
# from typing import Any
# from common.logging import get_logger

# logger = get_logger(__name__)

# # External SDKs
# try:
#     import openai
# except ImportError:
#     openai = None
#     logger.warning("openai SDK not found. Install with: pip install openai")

# try:
#     from google import genai
#     from google.genai import types
# except ImportError:
#     genai = None
#     types = None
#     logger.warning(
#         "google-generativeai SDK not found. Install with: pip install google-generativeai"
#     )

# from base.base_llm import BaseLLMProvider
# from schemas.llm_types import LLMResponse, ProviderError, ConfigurationError


# class OpenAIProvider(BaseLLMProvider):
#     def _validate_config(self) -> None:
#         if not openai:
#             raise ConfigurationError("OpenAI SDK not installed. Run `pip install openai`")

#         # if provider-specific required keys are present in extra, validate them here
#         # (no API key in config; secrets are read from env)
#         # example: require "deployment_id" for Azure usage stored in extra
#         if self.config.extra.get("require_deployment_id", False):
#             if not self.config.extra.get("deployment_id"):
#                 raise ConfigurationError(
#                     "deployment_id required in config.extra for OpenAI/Azure usage"
#                 )

#     def _initialize_client(self) -> Any:
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ConfigurationError("OPENAI_API_KEY environment variable not set")
#         # use openai.OpenAI or other init as before
#         return openai.OpenAI(api_key=api_key)

#     def generate(self, prompt: str, **kwargs) -> LLMResponse:
#         model = self.config.model_name
#         start_time = time.time()

#         try:
#             # Get provider-specific defaults from config.extra
#             top_p = kwargs.get("top_p", self.config.extra.get("top_p", 1.0))
#             frequency_penalty = kwargs.get(
#                 "frequency_penalty", self.config.extra.get("frequency_penalty", 0.0)
#             )
#             presence_penalty = kwargs.get(
#                 "presence_penalty", self.config.extra.get("presence_penalty", 0.0)
#             )

#             params = {
#                 "model": model,
#                 "messages": [{"role": "user", "content": prompt}],
#                 "temperature": kwargs.get("temperature", self.config.temperature),
#                 "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
#                 "top_p": top_p,
#                 "frequency_penalty": frequency_penalty,
#                 "presence_penalty": presence_penalty,
#             }

#             response = self.client.chat.completions.create(**params)

#             duration_ms = (time.time() - start_time) * 1000

#             return LLMResponse(
#                 content=response.choices[0].message.content,
#                 model_name=model,
#                 provider="openai",
#                 latency_ms=round(duration_ms, 2),
#                 token_usage={
#                     "prompt_tokens": response.usage.prompt_tokens,
#                     "completion_tokens": response.usage.completion_tokens,
#                     "total_tokens": response.usage.total_tokens,
#                 },
#                 metadata={"system_fingerprint": getattr(response, "system_fingerprint", None)},
#             )

#         except Exception as e:
#             logger.error(f"OpenAI API Error: {e}")
#             raise ProviderError(f"OpenAI generation failed: {str(e)}")


# class GeminiProvider(BaseLLMProvider):
#     def _validate_config(self) -> None:
#         if not genai:
#             raise ConfigurationError(
#                 "Google GenAI SDK not installed. Run `pip install google-generativeai`"
#             )
#         # validate provider-specific required keys in config.extra if needed
#         if self.config.extra.get("require_project_id", False):
#             if not self.config.extra.get("project_id"):
#                 raise ConfigurationError("project_id required in config.extra for Gemini Vertex AI")

#     def _initialize_client(self) -> Any:
#         # For Vertex AI integration, project_id should be in config.extra
#         project_id = self.config.extra.get("project_id")
#         if project_id:
#             location = self.config.extra.get("location", "us-central1")
#             return genai.Client(vertexai=True, project=project_id, location=location)

#         # For standard API key auth (still loaded from env)
#         api_key = os.getenv("GEMINI_API_KEY")
#         if not api_key:
#             raise ConfigurationError("GEMINI_API_KEY environment variable not set")
#         return genai.Client(api_key=api_key)

#     def generate(self, prompt: str, **kwargs) -> LLMResponse:
#         start_time = time.time()

#         try:
#             safety_settings = [
#                 types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
#                 types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
#                 types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
#                 types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
#             ]

#             # provider-specific defaults from config.extra
#             top_k = kwargs.get("top_k", self.config.extra.get("top_k", 40))
#             top_p = kwargs.get("top_p", self.config.extra.get("top_p", 1.0))

#             config_params = {
#                 "temperature": kwargs.get("temperature", self.config.temperature),
#                 "top_k": top_k,
#                 "top_p": top_p,
#                 "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
#                 "response_modalities": ["TEXT"],
#                 "safety_settings": safety_settings,
#             }

#             generate_content_config = types.GenerateContentConfig(**config_params)

#             contents = [
#                 types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
#             ]

#             response = self.client.models.generate_content(
#                 model=self.config.model_name,
#                 contents=contents,
#                 config=generate_content_config,
#             )

#             duration_ms = (time.time() - start_time) * 1000

#             usage_meta = {}
#             if hasattr(response, "usage_metadata"):
#                 usage_meta = {
#                     "prompt_tokens": response.usage_metadata.prompt_token_count,
#                     "completion_tokens": response.usage_metadata.candidates_token_count,
#                     "total_tokens": response.usage_metadata.total_token_count,
#                 }

#             return LLMResponse(
#                 content=response.text,
#                 model_name=self.config.model_name,
#                 provider="gemini",
#                 latency_ms=round(duration_ms, 2),
#                 token_usage=usage_meta,
#                 metadata={
#                     "finish_reason": (
#                         str(response.candidates[0].finish_reason)
#                         if response.candidates
#                         else "unknown"
#                     )
#                 },
#             )
#         except Exception as e:
#             logger.error(f"Gemini API Error: {e}")
#             raise ProviderError(f"Gemini generation failed: {str(e)}")
