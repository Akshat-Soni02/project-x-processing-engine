# # provides LLM-related types, configs and exceptions

# from dataclasses import dataclass, field
# from typing import Dict, Any
# from enum import Enum


# class LLMProviderType(Enum):
#     """Supported LLM providers"""

#     OPENAI = "openai"
#     GEMINI = "gemini"
#     MOCK = "mock"


# class LLMError(Exception):
#     """Base exception for LLM Service errors"""

#     pass


# class ConfigurationError(LLMError):
#     """Raised when API keys or configs are missing"""

#     pass


# class ProviderError(LLMError):
#     """Raised when the upstream provider fails"""

#     pass


# @dataclass
# class LLMResponse:
#     """Standardized LLM response object"""

#     content: str
#     model_name: str
#     provider: str
#     latency_ms: float
#     token_usage: Dict[str, int] = field(default_factory=dict)
#     metadata: Dict[str, Any] = field(default_factory=dict)


# @dataclass
# class LLMConfig:
#     """
#     Single canonical LLM config used across providers.

#     - model_name, temperature and max_tokens are common required fields.
#     - provider-specific settings (top_p, top_k, project_id, etc.) go into `extra`.
#     """

#     model_name: str
#     temperature: float = 0.7
#     max_tokens: int = 1024
#     # place provider/vendor specific settings here (not secrets)
#     extra: Dict[str, Any] = field(default_factory=dict)

#     def __post_init__(self):
#         if not self.model_name:
#             raise ConfigurationError("model_name is required for LLMConfig")
