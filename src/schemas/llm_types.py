# provides LLM-related types, configs and exceptions

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import time

class LLMProviderType(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"
    MOCK = "mock"  # for testing without costs

class LLMError(Exception):
    """Base exception for LLM Service errors"""
    pass

class ConfigurationError(LLMError):
    """Raised when API keys or configs are missing"""
    pass

class ProviderError(LLMError):
    """Raised when the upstream provider (OpenAI/Gemini) fails"""
    pass

@dataclass
class LLMResponse:
    """
    Standardized LLM response object.
    
    Attributes:
        content: The actual text response.
        model_name: The specific model used (e.g., gpt-4, gemini-pro).
        provider: The provider enum value.
        latency_ms: Time taken for the request in milliseconds.
        token_usage: Dictionary containing prompt_tokens, completion_tokens, total_tokens.
        metadata: Any extra raw data from the provider.
    """
    content: str
    model_name: str
    provider: str
    latency_ms: float
    token_usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LLMConfig:
    """Configuration object for the service"""
    provider: str
    api_key: str
    model_name: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = 1024
    # specific configs like 'top_p', 'top_k' go here
    extra_params: Dict[str, Any] = field(default_factory=dict)