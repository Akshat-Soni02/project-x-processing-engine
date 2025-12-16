# # stateless LLM Service with Provider Factory, Middleware Pipeline, and Error Handling

# from typing import Dict, Optional, Callable, List, Any, TypedDict
# from schemas.llm_types import LLMProviderType, LLMResponse, ConfigurationError
# from base.base_llm import BaseLLMProvider
# from common.logging import get_logger
# from util.llm_util import get_config, get_provider

# logger = get_logger(__name__)


# class ConfigDict(TypedDict):
#     """
#     A TypedDict for the configuration of the LLMService.
#     Ensures type-checking for configuration dictionaries.
#     """

#     provider: str
#     api_key: str
#     model_name: str
#     temperature: float
#     max_tokens: Optional[int]
#     extra_params: Dict[str, Any]


# class LLMService:
#     """
#     Stateless LLM Service.

#     Features:
#     - Provider Factory pattern
#     - Runtime provider switching
#     - Middleware pipeline (pre-processing/post-processing)
#     - Error boundaries
#     """

#     def __init__(self, config_dict: ConfigDict):
#         """
#         Initialize service with a dictionary config.

#         Args:
#             config_dict: Dictionary containing 'provider', 'api_key', etc.
#         """
#         self.raw_config = config_dict
#         self._provider_instance: Optional[BaseLLMProvider] = None

#         # Initialize the active provider
#         self._reload_provider(config_dict)

#         # Pipeline: List of functions that take text and return text
#         # Useful for cleaning prompts or PII masking before sending to LLM
#         self.pre_process_pipeline: List[Callable[[str], str]] = []

#         # Post-processing hooks (e.g., parsing JSON from the response)
#         self.post_process_pipeline: List[Callable[[LLMResponse], LLMResponse]] = []

#     def _reload_provider(self, config_dict: ConfigDict):
#         """Factory logic to instantiate the correct provider"""
#         try:
#             provider = config_dict.get("provider", None)

#             if provider == None:
#                 logger.critical("Missing provider for llm call. Using 'GEMINI' as Default")
#                 provider = "gemini"

#             provider_type = LLMProviderType(provider)
#             LLMConfig = get_config(provider_type)

#             # Create strongly typed config object
#             llm_config = LLMConfig(
#                 model_name=config_dict.get("model_name"),
#                 temperature=config_dict.get("temperature", 0.7),
#                 max_tokens=config_dict.get("max_tokens", 1024),
#                 extra_params=config_dict.get("extra_params", {}),
#             )

#             self._provider_instance = get_provider(provider_type)(llm_config)
#             logger.info(f"LLM Service initialized with provider: {provider_type.value}")

#         except ValueError as e:
#             raise ConfigurationError(f"Invalid provider specified: {e}")

#     def add_pre_processor(self, func: Callable[[str], str]):
#         """Add a function to modify prompt before sending to LLM"""
#         self.pre_process_pipeline.append(func)

#     def process(self, prompt: str, **kwargs) -> LLMResponse:
#         """
#         Main execution method.

#         1. Runs pre-processors
#         2. Calls LLM Provider
#         3. Runs post-processors
#         4. Handles errors
#         """
#         if not self._provider_instance:
#             raise ConfigurationError("Provider not initialized")

#         try:
#             # Pre-processing
#             current_prompt = prompt
#             for step in self.pre_process_pipeline:
#                 current_prompt = step(current_prompt)

#             logger.debug(
#                 f"Sending prompt to {self.raw_config.get('provider')}: {current_prompt[:50]}..."
#             )

#             # Execution
#             response = self._provider_instance.generate(current_prompt, **kwargs)

#             # Post-processing
#             for step in self.post_process_pipeline:
#                 response = step(response)

#             logger.info(
#                 f"Request successful. Latency: {response.latency_ms}ms. Tokens: {response.token_usage.get('total_tokens')}"
#             )
#             return response

#         except Exception as e:
#             logger.error(f"LLM Processing Error: {e}", exc_info=True)
#             raise e
