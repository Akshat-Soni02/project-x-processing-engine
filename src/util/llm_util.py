# def get_config(type: LLMProviderType):
#     """Retrieves the appropriate LLM configuration class based on the provider type.

#     This function acts as a factory for LLM configuration classes, returning the
#     specific configuration dataclass (e.g., OpenAIConfig, GeminiConfig) that
#     corresponds to the given LLMProviderType.

#     Args:
#         type: An enum member from LLMProviderType indicating the desired LLM provider.

#     Returns:
#         A dataclass type (e.g., OpenAIConfig, GeminiConfig) corresponding to the provider.

#     Raises:
#         ValueError: If an unsupported LLMProviderType is provided.
#     """
#     # if type == LLMProviderType.OPENAI:
#     #     return OpenAIConfig
#     # elif type == LLMProviderType.GEMINI:
#     #     return GeminiConfig
#     # else:
#     #     raise ValueError(f"Invalid provider type: {type}")


# def get_provider(type: LLMProviderType):
#     """Retrieves the appropriate LLM provider class based on the provider type.

#     This function acts as a factory for LLM provider classes, returning the
#     specific provider class (e.g., OpenAIProvider, GeminiProvider) that
#     corresponds to the given LLMProviderType.
#     """
#     if type == LLMProviderType.OPENAI:
#         return OpenAIProvider
#     elif type == LLMProviderType.GEMINI:
#         return GeminiProvider
#     else:
#         raise ValueError(f"Invalid provider type: {type}")
