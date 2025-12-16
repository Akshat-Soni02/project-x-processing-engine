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
        Tuple of (similarity_context_list, query_embedding_cost)
    """
    logger.debug("Preparing noteback similarity context...")

    search_anchors = context_response.get("search_anchors", [])

    if not search_anchors:
        logger.warning("No search anchors found in context response")
        return []

    logger.info(f"Processing {len(search_anchors)} search anchors for similarity search")
    similarity_context = []
    total_query_chars = 0

    for idx, anchor in enumerate(search_anchors, 1):
        anchor_preview = anchor[:50] + "..." if len(anchor) > 50 else anchor
        logger.debug(f"[Anchor {idx}/{len(search_anchors)}] Searching: {anchor_preview}")

        try:
            results, chars_used = vector_db.similarity_search(user_id="123", query=anchor, top_k=3)
            total_query_chars += chars_used

            logger.debug(f"[Anchor {idx}] Found {len(results)} similar sentences")

            for item in results:
                formatted = (
                    f"sentence_text: {item['sentence_text']}, value_score: {item['combined_score']}"
                )
                similarity_context.append(formatted)
                logger.debug(f"[Anchor {idx}] Added score={item['combined_score']:.4f}")

        except Exception as e:
            logger.error(f"[Anchor {idx}] Similarity search failed: {str(e)}", exc_info=True)
            continue

    logger.info(f"✓ Prepared {len(similarity_context)} similarity context items")
    return similarity_context


def format_sentences(context_response: dict) -> list:
    """
    Extract sentences from context response and format for noteback context.
    """
    logger.debug("Processing and formatting note sentences...")
    sentences_data = context_response.get("input_to_sentences", [])

    if not sentences_data:
        logger.warning("No sentences found in context response")
        return []

    formatted_sentences = []
    for idx, entry in enumerate(sentences_data, 1):
        formatted = f"{entry['sentence']}, importance_score: {entry['importance_score']}"
        formatted_sentences.append(formatted)
        logger.debug(f"[Sentence {idx}] Importance: {entry['importance_score']:.2f}")

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
