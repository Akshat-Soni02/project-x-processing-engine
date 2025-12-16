"""
Context preparation utilities for smart branch processing.
Handles vector database operations and context formatting (stateless).
"""

from common.logging import get_logger
from vector.db import Database

logger = get_logger(__name__)


def prepare_context_for_noteback(context_response: dict, vector_db: Database) -> list:
    """
    Perform similarity search on context response for noteback processing.

    Args:
        context_response: Response from context preparation LLM call
        vector_db: Initialized Database instance

    Returns:
        List of similarity context strings (empty list on error)
    """
    logger.debug("Preparing noteback similarity context...")

    # Validate inputs
    if context_response is None or not isinstance(context_response, dict):
        logger.error("Invalid context response - must be a dict")
        return []

    if vector_db is None:
        logger.error("Vector database not initialized")
        return []

    search_anchors = context_response.get("search_anchors", [])

    if not search_anchors:
        logger.warning("No search anchors found in context response")
        return []

    if not isinstance(search_anchors, list):
        logger.error(f"Invalid search_anchors type: {type(search_anchors).__name__}, expected list")
        return []

    logger.info(f"Processing {len(search_anchors)} search anchors for similarity search")
    similarity_context = []
    total_query_chars = 0
    failed_anchors = 0

    for idx, anchor in enumerate(search_anchors, 1):
        try:
            # Validate anchor
            if anchor is None or not isinstance(anchor, str):
                logger.warning(
                    f"[Anchor {idx}] Invalid anchor type: {type(anchor).__name__}, skipping"
                )
                failed_anchors += 1
                continue

            anchor_preview = anchor[:50] + "..." if len(anchor) > 50 else anchor
            logger.debug(f"[Anchor {idx}/{len(search_anchors)}] Searching: {anchor_preview}")

            results, chars_used = vector_db.similarity_search(user_id="123", query=anchor, top_k=3)
            total_query_chars += chars_used

            if results is None:
                logger.warning(f"[Anchor {idx}] No results from similarity search")
                continue

            logger.debug(f"[Anchor {idx}] Found {len(results)} similar sentences")

            for item in results:
                try:
                    if (
                        not isinstance(item, dict)
                        or "sentence_text" not in item
                        or "combined_score" not in item
                    ):
                        logger.warning(f"[Anchor {idx}] Invalid result item structure, skipping")
                        continue

                    formatted = f"sentence_text: {item['sentence_text']}, value_score: {item['combined_score']}"
                    similarity_context.append(formatted)
                    logger.debug(f"[Anchor {idx}] Added score={item['combined_score']:.4f}")
                except Exception as e:
                    logger.warning(f"[Anchor {idx}] Failed to process result item: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"[Anchor {idx}] Similarity search failed: {str(e)}", exc_info=True)
            failed_anchors += 1
            continue

    if failed_anchors > 0:
        logger.warning(f"Failed to process {failed_anchors}/{len(search_anchors)} anchors")

    logger.info(f"✓ Prepared {len(similarity_context)} similarity context items")
    return similarity_context


def format_sentences(context_response: dict) -> list:
    """
    Extract sentences from context response and format for noteback context.

    Args:
        context_response: Response dict from context preparation

    Returns:
        List of formatted sentence strings (empty list on error)
    """
    logger.debug("Processing and formatting note sentences...")

    # Validate input
    if context_response is None or not isinstance(context_response, dict):
        logger.error("Invalid context response - must be a dict")
        return []

    sentences_data = context_response.get("input_to_sentences", [])

    if not sentences_data:
        logger.warning("No sentences found in context response")
        return []

    if not isinstance(sentences_data, list):
        logger.error(f"Invalid sentences_data type: {type(sentences_data).__name__}, expected list")
        return []

    formatted_sentences = []
    failed_sentences = 0

    for idx, entry in enumerate(sentences_data, 1):
        try:
            # Validate entry
            if entry is None or not isinstance(entry, dict):
                logger.warning(
                    f"[Sentence {idx}] Invalid entry type: {type(entry).__name__}, skipping"
                )
                failed_sentences += 1
                continue

            if "sentence" not in entry or "importance_score" not in entry:
                logger.warning(
                    f"[Sentence {idx}] Missing required fields (sentence, importance_score)"
                )
                failed_sentences += 1
                continue

            sentence_text = entry["sentence"]
            importance_score = entry["importance_score"]

            if not isinstance(sentence_text, str):
                logger.warning(
                    f"[Sentence {idx}] Invalid sentence type: {type(sentence_text).__name__}"
                )
                failed_sentences += 1
                continue

            if not isinstance(importance_score, (int, float)):
                logger.warning(
                    f"[Sentence {idx}] Invalid importance_score type: {type(importance_score).__name__}"
                )
                failed_sentences += 1
                continue

            formatted = f"{sentence_text}, importance_score: {importance_score:.2f}"
            formatted_sentences.append(formatted)
            logger.debug(f"[Sentence {idx}] Importance: {importance_score:.2f}")

        except Exception as e:
            logger.error(f"[Sentence {idx}] Failed to format sentence: {str(e)}", exc_info=True)
            failed_sentences += 1
            continue

    if failed_sentences > 0:
        logger.warning(f"Failed to format {failed_sentences}/{len(sentences_data)} sentences")

    logger.info(f"✓ Formatted {len(formatted_sentences)} sentences for noteback context")
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
