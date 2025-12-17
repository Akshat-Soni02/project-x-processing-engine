# # base class for LLM providers

# from abc import ABC, abstractmethod
# from typing import Any
# from schemas.llm_types import (
#     LLMResponse,
#     LLMConfig,
# )


# class BaseLLMProvider(ABC):
#     """
#     Abstract base class for LLM providers.
#     Stateless - no session management. Each call is independent.

#     Credentials are injected separately from config (env / secret manager).
#     """

#     def __init__(self, config: LLMConfig):
#         self.config = config
#         self._validate_config()
#         self.client = self._initialize_client()

#     @abstractmethod
#     def _validate_config(self) -> None:
#         """
#         Validate config-specific requirements.
#         Raise ConfigurationError if invalid.
#         """
#         pass

#     @abstractmethod
#     def _initialize_client(self) -> Any:
#         """
#         Initialize the third-party SDK client.
#         Credentials should be loaded from environment or credential manager here.
#         """
#         pass

#     @abstractmethod
#     def generate(self, prompt: str, **kwargs) -> LLMResponse:
#         """
#         Generate completion from prompt.

#         Args:
#             prompt: The input text.
#             **kwargs: Runtime overrides (temperature, max_tokens, etc.)

#         Returns:
#             LLMResponse with standardized output.
#         """
#         pass

#     def _merge_params(self, **kwargs) -> dict:
#         """
#         Merge runtime kwargs with config defaults.
#         Runtime kwargs take precedence.
#         Provider-specific defaults should be read from config.extra.
#         """
#         return {
#             "temperature": kwargs.get("temperature", self.config.temperature),
#             "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
#             **kwargs,
#         }
