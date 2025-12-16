from config import (
    Llm_Call,
    User_Input_Type,
    Stt_Call_Config,
    Context_Call_Config,
    Noteback_Call_Config,
)
from common.utils import read_file
from typing import Optional, Sequence


def get_llm_input(
    llm_call: Llm_Call,
    input: Optional[bytes] = None,
    input_type: Optional[User_Input_Type] = None,
    replace: Optional[Sequence[dict]] = None,
):

    if llm_call == Llm_Call.STT:
        return prepare_llm_input(Stt_Call_Config, input, input_type, replace)
    if llm_call == Llm_Call.SMART:
        return prepare_llm_input(Context_Call_Config, input, input_type, replace)
    if llm_call == Llm_Call.NOTEBACK:
        return prepare_llm_input(Noteback_Call_Config, input, input_type, replace)
    return None


def prepare_llm_input(
    input_config: dict,
    input: Optional[bytes] = None,
    input_type: Optional[User_Input_Type] = None,
    replace: Optional[Sequence[dict]] = None,
) -> dict:
    """
    Docstring for prepare_llm_input

    :param input_config: Description
    :type input_config: dict
    :param replace: Description
    :type replace: dict

    replace: [{
        "type": prompt/sys,
        "replace_key": "your replace key",
        "replace_value": "your replace value"
    }]
    """
    # take input as the configs and give structured dict output after reading files
    prompt_file_path = input_config.get("PROMPT_FILE_PATH", None)
    system_instruction_file_path = input_config.get("SYSTEM_INSTRUCTION_FILE_PATH", None)
    response_schema_file_path = input_config.get("RESPONSE_SCHEMA_FILE_PATH", None)

    prompt = None
    system_instruction = None
    response_schema = None

    if prompt_file_path:
        prompt = read_file(prompt_file_path)
    if system_instruction_file_path:
        system_instruction = read_file(system_instruction_file_path)
    if response_schema_file_path:
        response_schema = read_file(response_schema_file_path, is_json=True)

    if replace:
        for item in replace:
            if item["type"] == "prompt":
                if prompt is None:
                    continue
                prompt = prompt.replace(item["replace_key"], item["replace_value"])
            elif item["type"] == "sys":
                if system_instruction is None:
                    continue
                system_instruction = system_instruction.replace(
                    item["replace_key"], item["replace_value"]
                )

    llm_input = {
        "model": input_config.get("model"),
        "token_limit": input_config.get("token_limit"),
        "prompt": prompt,
        "system_instruction": system_instruction,
        "response_schema": response_schema,
    }

    if input and input_type:
        llm_input["input_type"] = input_type
        llm_input["user_data"] = input

    return llm_input
