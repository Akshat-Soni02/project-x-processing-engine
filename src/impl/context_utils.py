"""
Context preparation utilities for smart branch processing.
Handles vector database operations and formatting for contextually-aware LLM generation.
"""

from common.logging import get_logger
from db.db import Database
from pipeline.exceptions import FatalPipelineError, TransientPipelineError

logger = get_logger(__name__)


def prepare_context_for_noteback(context_response: dict, vector_db: Database) -> list:
    """
    Perform multi-anchor similarity search using context preparation output.

    Args:
        context_response (dict): Parsed JSON response from context LLM.
        vector_db (Database): Initialized vector database instance.

    Returns:
        list: List of formatted similarity context strings for prompting.
    """
    logger.debug("Preparing noteback similarity context")

    if context_response is None or not isinstance(context_response, dict):
        logger.error(
            "Invalid context response format: Expected dict",
            extra={"type": type(context_response).__name__},
        )
        raise FatalPipelineError("Invalid context response format: Expected dict")

    if vector_db is None:
        logger.error("Vector database not initialized")
        raise FatalPipelineError("Vector database not initialized")

    search_anchors = context_response.get("search_anchors", [])

    if not search_anchors:
        logger.warning("No search anchors found in context response")
        raise FatalPipelineError("No search anchors found in context response")

    if not isinstance(search_anchors, list):
        logger.error(
            "Invalid search_anchors format: Expected list",
            extra={"type": type(search_anchors).__name__},
        )
        raise FatalPipelineError("Invalid search_anchors format: Expected list")

    similarity_context = []
    total_query_chars = 0
    failed_anchors = 0

    for idx, anchor in enumerate(search_anchors, 1):
        try:
            if anchor is None or not isinstance(anchor, str):
                logger.warning(
                    "Invalid anchor type", extra={"index": idx, "type": type(anchor).__name__}
                )
                failed_anchors += 1
                continue

            logger.debug(
                "Searching similarity anchor", extra={"index": idx, "total": len(search_anchors)}
            )

            results, chars_used = vector_db.similarity_search(user_id="123", query=anchor, top_k=3)
            total_query_chars += chars_used

            if results is None:
                logger.warning("No results from similarity search for anchor", extra={"index": idx})
                raise FatalPipelineError("No results from similarity search for anchor")

            for item in results:
                try:
                    if (
                        not isinstance(item, dict)
                        or "sentence_text" not in item
                        or "combined_score" not in item
                    ):
                        logger.warning("Invalid result item structure", extra={"index": idx})
                        raise FatalPipelineError("Invalid result item structure")

                    formatted = f"sentence_text: {item['sentence_text']}, value_score: {item['combined_score']}"
                    similarity_context.append(formatted)
                except Exception as e:
                    logger.warning(
                        "Failed to process result item", extra={"index": idx, "error": str(e)}
                    )
                    raise FatalPipelineError("Failed to process result item")

        except Exception as e:
            logger.error(
                "Similarity search failed", extra={"index": idx, "error": str(e)}, exc_info=True
            )
            failed_anchors += 1
            raise FatalPipelineError("Similarity search failed")

    if failed_anchors > 0:
        logger.warning(
            "Failed to process some search anchors",
            extra={"failed": failed_anchors, "total": len(search_anchors)},
        )

    logger.debug(
        "Similarity context preparation completed", extra={"count": len(similarity_context)}
    )
    return similarity_context


def format_sentences(context_response: dict) -> list:
    """
    Extract and format current note sentences with importance scores.

    Args:
        context_response (dict): Response dict from context preparation.

    Returns:
        list: Formatted sentence strings including importance metrics.
    """
    logger.debug("Formatting note sentences")

    if context_response is None or not isinstance(context_response, dict):
        logger.error("Invalid context response format: Expected dict")
        raise FatalPipelineError("Invalid context response format: Expected dict")

    sentences_data = context_response.get("input_to_sentences", [])

    if not sentences_data:
        logger.warning("No sentences found in context response")
        raise FatalPipelineError("No sentences found in context response")

    if not isinstance(sentences_data, list):
        logger.error(
            "Invalid sentences_data format: Expected list",
            extra={"type": type(sentences_data).__name__},
        )
        raise FatalPipelineError("Invalid sentences_data format: Expected list")

    formatted_sentences = []
    failed_sentences = 0

    for idx, entry in enumerate(sentences_data, 1):
        try:
            if entry is None or not isinstance(entry, dict):
                logger.warning(
                    "Invalid entry type", extra={"index": idx, "type": type(entry).__name__}
                )
                failed_sentences += 1
                raise FatalPipelineError("Invalid entry type")

            if "sentence" not in entry or "importance_score" not in entry:
                logger.warning("Missing required fields in sentence entry", extra={"index": idx})
                failed_sentences += 1
                raise FatalPipelineError("Missing required fields in sentence entry")

            sentence_text = entry["sentence"]
            importance_score = entry["importance_score"]

            if not isinstance(sentence_text, str):
                logger.warning(
                    "Invalid sentence text type",
                    extra={"index": idx, "type": type(sentence_text).__name__},
                )
                failed_sentences += 1
                raise FatalPipelineError("Invalid sentence text type")

            if not isinstance(importance_score, (int, float)):
                logger.warning(
                    "Invalid importance_score type",
                    extra={"index": idx, "type": type(importance_score).__name__},
                )
                failed_sentences += 1
                raise TransientPipelineError("Invalid importance_score type")

            formatted = f"{sentence_text}, importance_score: {importance_score:.2f}"
            formatted_sentences.append(formatted)

        except Exception as e:
            logger.error(
                "Failed to format sentence", extra={"index": idx, "error": str(e)}, exc_info=True
            )
            failed_sentences += 1
            raise FatalPipelineError("Failed to format sentence")

    if failed_sentences > 0:
        logger.warning(
            "Failed to format some sentences",
            extra={"failed": failed_sentences, "total": len(sentences_data)},
        )

    logger.debug("Sentence formatting completed", extra={"count": len(formatted_sentences)})
    return formatted_sentences


# Depricated
# def save_sentences_to_vector_db(context_response: dict, vector_db: Database) -> tuple:
#     """
#     Extract sentences from context response and save to vector database.

#     Args:
#         context_response: Response from context preparation LLM call
#         vector_db: Initialized Database instance

#     Returns:
#         Tuple of (formatted_sentences_list, embedding_cost)
#     """
#     logger.debug("Processing and saving new note sentences...")

#     sentences_data = context_response.get("input_to_sentences", [])

#     if not sentences_data:
#         logger.warning("No sentences found in context response")
#         return [], 0.0

#     logger.info(f"Inserting {len(sentences_data)} sentences into vector database...")

#     try:
#         total_chars = vector_db.insert_sentences(
#             user_id="123",
#             note_id=str(__import__("numpy").random.randint(1, 9999)),
#             sentences=[
#                 {
#                     "sentence_index": idx,
#                     "sentence_text": entry["sentence"],
#                     "importance_score": entry["importance_score"],
#                 }
#                 for idx, entry in enumerate(sentences_data)
#             ],
#         )
#         logger.info(f"✓ Inserted {len(sentences_data)} sentences into vector DB")

#     except Exception as e:
#         logger.error(f"✗ Failed to insert sentences: {str(e)}", exc_info=True)
#         raise

#     # Format sentences for noteback context
#     formatted_sentences = []
#     for idx, entry in enumerate(sentences_data, 1):
#         formatted = f"{entry['sentence']}, importance_score: {entry['importance_score']}"
#         formatted_sentences.append(formatted)
#         logger.debug(f"[Sentence {idx}] Importance: {entry['importance_score']:.2f}")

#     logger.info(f"✓ Formatted {len(formatted_sentences)} sentences for noteback context")

#     # Calculate embedding cost (you'll need cost_estimator for this)
#     # For now, returning 0.0 - integrate cost calculation as needed
#     return formatted_sentences, 0.0
