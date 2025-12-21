# import asyncio
# from unittest.mock import MagicMock
# from src.impl.gemini import GeminiProvider
# from src.impl.llm_processor import call_llm
# from src.pipeline.exceptions import FatalPipelineError, TransientPipelineError
# from google import genai
# from collections import namedtuple

# # Mock response structure
# Candidate = namedtuple('Candidate', ['finish_reason'])
# Response = namedtuple('Response', ['candidates', 'text', 'usage_metadata'])
# UsageMetadata = namedtuple('UsageMetadata', ['candidates_token_count', 'thoughts_token_count'])

# def test_transient_error_handling():
#     print("Testing Transient Error Handling...")
#     mock_client = MagicMock()
#     provider = GeminiProvider(mock_client)

#     # Simulate Server Error (Transient)
#     # genai expects {"error": {"message": "..."}} structure
#     error_json = {"error": {"message": "Internal Server Error"}}
#     mock_client.models.generate_content.side_effect = genai.errors.ServerError(503, error_json)

#     try:
#         call_llm(provider, {"model": "test", "prompt": "test", "token_limit": 100, "system_instruction": "test"}, "TEST")
#         print("FAILED: Expected TransientPipelineError was not raised")
#     except TransientPipelineError:
#         print("PASSED: TransientPipelineError caught correctly")
#     except Exception as e:
#         print(f"FAILED: Caught unexpected exception: {type(e).__name__} - {e}")

# def test_fatal_error_handling():
#     print("\nTesting Fatal Error Handling...")
#     mock_client = MagicMock()
#     provider = GeminiProvider(mock_client)

#     # Simulate Client Error (Fatal 400)
#     error_json = {"error": {"message": "Invalid Argument"}}
#     mock_client.models.generate_content.side_effect = genai.errors.ClientError(400, error_json)

#     try:
#         call_llm(provider, {"model": "test", "prompt": "test", "token_limit": 100, "system_instruction": "test"}, "TEST")
#         print("FAILED: Expected FatalPipelineError was not raised")
#     except FatalPipelineError:
#         print("PASSED: FatalPipelineError caught correctly")
#     except Exception as e:
#         print(f"FAILED: Caught unexpected exception: {type(e).__name__} - {e}")

# def test_finish_reason_handling():
#     print("\nTesting Finish Reason Handling...")
#     mock_client = MagicMock()
#     provider = GeminiProvider(mock_client)

#     # Simulate SAFETY block (Fatal)
#     provider.calculate_metrics = MagicMock(return_value={})

#     mock_response = Response(
#         candidates=[Candidate(finish_reason="SAFETY")],
#         text="Blocked content",
#         usage_metadata=UsageMetadata(candidates_token_count=10, thoughts_token_count=0)
#     )
#     mock_client.models.generate_content.return_value = mock_response
#     mock_client.models.generate_content.side_effect = None

#     try:
#         call_llm(provider, {"model": "test", "prompt": "test", "token_limit": 100, "system_instruction": "test"}, "TEST")
#         print("FAILED: Expected FatalPipelineError for SAFETY was not raised")
#     except FatalPipelineError:
#         print("PASSED: FatalPipelineError for SAFETY caught correctly")
#     except Exception as e:
#         print(f"FAILED: Caught unexpected exception: {type(e).__name__} - {e}")

# if __name__ == "__main__":
#     test_transient_error_handling()
#     test_fatal_error_handling()
#     test_finish_reason_handling()
