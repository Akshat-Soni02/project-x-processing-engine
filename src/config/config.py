"""
Configuration constants and enums for LLM execution.
Defines model IDs, input types, and file paths for prompts and schemas.
"""

from enum import Enum


class Models:
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_0_FLASH = "gemini-2.0-flash-001"
    GEMINI_2_5_PRO = "gemini-2.5-pro"


class Llm_Call:
    STT = "stt"
    SMART = "smart"
    NOTEBACK = "noteback"


class User_Input_Type(str, Enum):
    AUDIO_WAV = "audio/wav"
    TEXT_PLAIN = "text/plain"


class Stt_Call_Config:
    MODEL = Models.GEMINI_2_5_FLASH
    TOKEN_LIMIT = 65535
    PROMPT_FILE_PATH = "src/prompt/stt/stt_prompt.txt"
    SYSTEM_INSTRUCTION_FILE_PATH = "src/prompt/stt/stt_system_instruction.txt"
    RESPONSE_SCHEMA_FILE_PATH = "src/prompt/stt/stt_response_schema.json"


class Context_Call_Config:
    MODEL = Models.GEMINI_2_5_PRO
    TOKEN_LIMIT = 65535
    PROMPT_FILE_PATH = "src/prompt/context/context_prompt.txt"
    SYSTEM_INSTRUCTION_FILE_PATH = "src/prompt/context/context_system_instruction.txt"
    RESPONSE_SCHEMA_FILE_PATH = "src/prompt/context/context_response_schema.json"


class Noteback_Call_Config:
    MODEL = Models.GEMINI_2_5_FLASH
    TOKEN_LIMIT = 65535
    PROMPT_FILE_PATH = "src/prompt/noteback/noteback_prompt.txt"
    SYSTEM_INSTRUCTION_FILE_PATH = "src/prompt/noteback/noteback_system_instruction.txt"
    RESPONSE_SCHEMA_FILE_PATH = "src/prompt/noteback/noteback_response_schema.json"
