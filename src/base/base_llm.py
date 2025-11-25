# base class for LLM providers

from abc import ABC, abstractmethod
from typing import Dict, Any
from schemas.llm_types import LLMResponse, LLMConfig

class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    Ensures that switching providers doesn't break the main application logic.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._validate_config()
        self.client = self._initialize_client()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate specific config requirements (e.g., API keys)"""
        pass

    @abstractmethod
    def _initialize_client(self) -> Any:
        """Initialize the third-party SDK client"""
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate completion from prompt.
        
        Args:
            prompt: The input text.
            **kwargs: Override config parameters for a single request.
        """
        pass