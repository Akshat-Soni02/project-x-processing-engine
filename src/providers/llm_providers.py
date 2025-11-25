# LLM provider implementations for OpenAI and Gemini

import time
from typing import Any, Dict
import logging

# External SDKs
try:
    import openai
except ImportError:
    openai = None
    print("Warning: openai SDK not found. Install with: pip install openai")

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    print("Warning: google-generativeai SDK not found. Install with: pip install google-generativeai")

from base.base_llm import BaseLLMProvider
from schemas.llm_types import LLMResponse, LLMConfig, ProviderError, ConfigurationError

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    def _validate_config(self) -> None:
        if not self.config.api_key:
            raise ConfigurationError("OpenAI API key is missing")
        if not openai:
            raise ConfigurationError("OpenAI SDK not installed. Run `pip install openai`")

    def _initialize_client(self) -> Any:
        return openai.OpenAI(api_key=self.config.api_key)

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        model = kwargs.get("model", self.config.model_name) or "gpt-3.5-turbo"
        start_time = time.time()
        
        try:
            # Merge default config with runtime kwargs
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                **self.config.extra_params
            }
            
            response = self.client.chat.completions.create(**params)
            
            duration_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model_name=model,
                provider="openai",
                latency_ms=round(duration_ms, 2),
                token_usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                metadata={"system_fingerprint": response.system_fingerprint}
            )
            
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            raise ProviderError(f"OpenAI generation failed: {str(e)}")


class GeminiProvider(BaseLLMProvider):
    def _validate_config(self) -> None:
        if not self.config.api_key:
            raise ConfigurationError("Gemini API key is missing")
        if not genai:
            raise ConfigurationError("Google GenAI SDK not installed. Run `pip install google-generativeai`")

    def _initialize_client(self) -> Any:
        # genai.configure(api_key=self.config.api_key)
        
        # model_name = self.config.model_name or "gemini-1.5-flash"

        client = genai.Client(
                vertexai=True,
                project="documind-474519",
                location="us-central1"
        )
        return client

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        start_time = time.time()
        
        try:
            safety_settings = [
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ]

            config_params = {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "top_k": kwargs.get("top_k", 40),
                "top_p": kwargs.get("top_p", 0.9),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "response_modalities": ["TEXT"],
                "safety_settings": safety_settings
            }

            # if response_schema:
            #     config_params["response_schema"] = response_schema
            #     config_params["response_mime_type"] = "application/json"
                
            # if log_prob > 0:
            #     config_params["response_logprobs"] = True
            #     config_params["logprobs"] = log_prob

            generate_content_config = types.GenerateContentConfig(**config_params)
            gen_config = generate_content_config

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt)
                    ]
                ),
            ]

            response = self.client.models.generate_content(
                        model=self.config.model_name or "gemini-1.5-flash",
                        contents=contents,
                        config=gen_config,
                    )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Gemini usage metadata handling varies, simpler implementation here
            usage_meta = {}
            if hasattr(response, 'usage_metadata'):
                usage_meta = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count
                }

            return LLMResponse(
                content=response.text,
                model_name=self.config.model_name or "gemini-1.5-flash",
                provider="gemini",
                latency_ms=round(duration_ms, 2),
                token_usage=usage_meta,
                metadata={"finish_reason": str(response.candidates[0].finish_reason) if response.candidates else "unknown"}
            )
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            raise ProviderError(f"Gemini generation failed: {str(e)}")