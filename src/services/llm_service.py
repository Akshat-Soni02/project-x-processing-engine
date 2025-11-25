# stateless LLM Service with Provider Factory, Middleware Pipeline, and Error Handling

import logging
from typing import Dict, Optional, Callable, List, Tuple, Any
from schemas.llm_types import LLMConfig, LLMProviderType, LLMResponse, ConfigurationError
from providers.llm_providers import OpenAIProvider, GeminiProvider
from base.base_llm import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMService:
    """
    Stateless LLM Service.
    
    Features:
    - Provider Factory pattern
    - Runtime provider switching
    - Middleware pipeline (pre-processing/post-processing)
    - Error boundaries
    """

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize service with a dictionary config.
        
        Args:
            config_dict: Dictionary containing 'provider', 'api_key', etc.
        """
        self.raw_config = config_dict
        self._provider_instance: Optional[BaseLLMProvider] = None
        
        # Initialize the active provider
        self._reload_provider(config_dict)

        # Pipeline: List of functions that take text and return text
        # Useful for cleaning prompts or PII masking before sending to LLM
        self.pre_process_pipeline: List[Callable[[str], str]] = []
        
        # Post-processing hooks (e.g., parsing JSON from the response)
        self.post_process_pipeline: List[Callable[[LLMResponse], LLMResponse]] = []

    def _reload_provider(self, config_dict: Dict[str, Any]):
        """Factory logic to instantiate the correct provider"""
        try:
            provider_type = LLMProviderType(config_dict.get("provider", "openai"))
            api_key = config_dict.get("api_key", "")
            
            # Create strongly typed config object
            llm_config = LLMConfig(
                provider=provider_type.value,
                api_key=api_key,
                model_name=config_dict.get("model_name"),
                temperature=config_dict.get("temperature", 0.7),
                max_tokens=config_dict.get("max_tokens", 1024),
                extra_params=config_dict.get("extra_params", {})
            )

            if provider_type == LLMProviderType.OPENAI:
                self._provider_instance = OpenAIProvider(llm_config)
            elif provider_type == LLMProviderType.GEMINI:
                self._provider_instance = GeminiProvider(llm_config)
            else:
                raise ConfigurationError(f"Provider {provider_type} not implemented yet")
                
            logger.info(f"LLM Service initialized with provider: {provider_type.value}")
            
        except ValueError as e:
            raise ConfigurationError(f"Invalid provider specified: {e}")

    def add_pre_processor(self, func: Callable[[str], str]):
        """Add a function to modify prompt before sending to LLM"""
        self.pre_process_pipeline.append(func)

    def process(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Main execution method.
        
        1. Runs pre-processors
        2. Calls LLM Provider
        3. Runs post-processors
        4. Handles errors
        """
        if not self._provider_instance:
            raise ConfigurationError("Provider not initialized")

        try:
            # 1. Pre-processing
            current_prompt = prompt
            for step in self.pre_process_pipeline:
                current_prompt = step(current_prompt)
            
            logger.debug(f"Sending prompt to {self.raw_config.get('provider')}: {current_prompt[:50]}...")

            # 2. Execution
            response = self._provider_instance.generate(current_prompt, **kwargs)

            # 3. Post-processing
            for step in self.post_process_pipeline:
                response = step(response)
            
            logger.info(f"Request successful. Latency: {response.latency_ms}ms. Tokens: {response.token_usage.get('total_tokens')}")
            return response

        except Exception as e:
            logger.error(f"LLM Processing Error: {e}", exc_info=True)
            # Re-raise or return a standardized error response object depending on your needs
            raise e