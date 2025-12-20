"""
Vector database interface for storing and searching note embeddings.
Uses PostgreSQL with pgvector for efficient similarity search and context retrieval.
"""

import psycopg
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from common.logging import get_logger

logger = get_logger(__name__)


# TODO: Migrate module from vertexai.language_models to google-genai
class Database:
    """
    Handles connection and operations with the vector database.
    Provides methods for embedding generation, data insertion, and similarity search.
    """

    def __init__(self):
        """
        Establish connection to the PostgreSQL database and initialize the embedding model.
        """
        self.conn = psycopg.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()
        logger.debug("Database connection established")

        self.embedding_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
        self.embedding_dimensionality = 1536

    def __del__(self):
        """
        Gracefully close the database connection on object destruction.
        """
        try:
            self.cursor.close()
            self.conn.close()
            logger.debug("Database connection closed")
        except Exception:
            pass

    def _generate_query_embedding(self, text: str) -> tuple[list[float], int]:
        """
        Generate an embedding for a search query.

        Args:
            text (str): Query text.

        Returns:
            tuple: (embedding_values, char_count)
        """
        dimensionality = self.embedding_dimensionality
        task = "RETRIEVAL_QUERY"
        model = self.embedding_model

        text_input = TextEmbeddingInput(text, task)
        if dimensionality:
            embedding_response = model.get_embeddings(
                [text_input], output_dimensionality=dimensionality
            )
        else:
            embedding_response = model.get_embeddings([text_input])

        return embedding_response[0].values, len(text)

    def _generate_sentence_embedding(self, sentence: str) -> tuple[list[float], int]:
        """
        Generate an embedding for a document sentence.

        Args:
            sentence (str): Sentence text.

        Returns:
            tuple: (embedding_values, char_count)
        """
        dimensionality = self.embedding_dimensionality
        task = "RETRIEVAL_DOCUMENT"
        model = self.embedding_model

        text_input = TextEmbeddingInput(sentence, task)
        if dimensionality:
            embedding_response = model.get_embeddings(
                [text_input], output_dimensionality=dimensionality
            )
        else:
            embedding_response = model.get_embeddings([text_input])

        return embedding_response[0].values, len(sentence)

    def insert_sentences(self, user_id: str, note_id: str, sentences: list[dict]) -> int:
        """
        Insert multiple sentences with their embeddings into the database.

        Args:
            user_id (str): ID of the user owning the note.
            note_id (str): ID of the note.
            sentences (list[dict]): List of dictionaries containing sentence text and metadata.

        Returns:
            int: Total characters processed for billing/tracking purposes.
        """
        insert_query = """
        INSERT INTO user_notes (user_id, note_id, sentence_index, sentence_text, embedding, language, importance_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, note_id, sentence_index) DO NOTHING;
        """
        total_chars = 0
        for sentence in sentences:
            sentence_index = sentence["sentence_index"]
            sentence_text = sentence["sentence_text"]
            language = sentence.get("language", "en")
            embedding, char_count = self._generate_sentence_embedding(sentence_text)
            total_chars += char_count
            importance_score = sentence.get("importance_score", 0)
            self.cursor.execute(
                insert_query,
                (
                    user_id,
                    note_id,
                    sentence_index,
                    sentence_text,
                    embedding,
                    language,
                    importance_score,
                ),
            )
        logger.debug(
            "Sentences inserted into database",
            extra={"count": len(sentences), "user_id": user_id, "note_id": note_id},
        )
        return total_chars

    def similarity_search(self, user_id: str, query: str, top_k: int = 5) -> tuple[list[dict], int]:
        """
        Perform a hybrid similarity search considering distance, importance, and recency.

        Args:
            user_id (str): User ID context.
            query (str): Search query text.
            top_k (int): Number of top results to return.

        Returns:
            tuple: (List of result dictionaries, query character count)
        """
        query_embedding, query_chars = self._generate_query_embedding(query)

        search_query = """
        WITH ranked_notes AS (
            SELECT
                sentence_index,
                sentence_text,
                embedding <=> %s::vector AS distance,
                importance_score,
                EXTRACT(EPOCH FROM timestamp) AS ts_epoch
            FROM user_notes
            WHERE user_id = %s
        )
        , stats AS (
            SELECT
                MAX(importance_score) AS max_importance,
                MIN(ts_epoch) AS min_ts,
                MAX(ts_epoch) AS max_ts
            FROM ranked_notes
        )
        SELECT
            rn.sentence_index,
            rn.sentence_text,
            rn.distance,
            rn.importance_score,
            rn.ts_epoch,
            (1 / (1 + rn.distance)) * 0.6 +
            (rn.importance_score / NULLIF(s.max_importance, 0)) * 0.2 +
            ((rn.ts_epoch - s.min_ts) / NULLIF(s.max_ts - s.min_ts, 0)) * 0.2 AS combined_score
        FROM ranked_notes rn
        CROSS JOIN stats s
        ORDER BY combined_score DESC
        LIMIT %s;
        """

        self.cursor.execute(search_query, (str(query_embedding), user_id, top_k))
        results = self.cursor.fetchall()

        similar_sentences = [
            {
                "sentence_index": row[0],
                "sentence_text": row[1],
                "distance": row[2],
                "importance_score": row[3],
                "timestamp_epoch": row[4],
                "combined_score": row[5],
            }
            for row in results
        ]
        logger.debug(
            "Similarity search performed", extra={"user_id": user_id, "query_preview": query[:50]}
        )
        return similar_sentences, query_chars

    def get_sentence(self, filter_params: dict) -> dict:
        """
        Retrieve a specific sentence or set of sentences based on filters.

        Args:
            filter_params (dict): Filters (user_id Required, note_id, sentence_index).

        Returns:
            dict: The first matching sentence or None.
        """
        user_id = filter_params.get("user_id")
        note_id = filter_params.get("note_id")
        sentence_index = filter_params.get("sentence_index")

        search_part = ""
        params = [user_id]

        if note_id is not None:
            search_part += "AND note_id = %s "
            params.append(note_id)
        if sentence_index is not None:
            search_part += "AND sentence_index = %s "
            params.append(sentence_index)

        select_query = f"""
        SELECT sentence_index, sentence_text, importance_score
        FROM user_notes
        WHERE user_id = %s {search_part};
        """

        self.cursor.execute(select_query, tuple(params))
        result = self.cursor.fetchone()

        if result:
            idx, text, score = result
            return {
                "sentence_index": idx,
                "sentence_text": text,
                "importance_score": score,
            }
        return None

    def delete_sentences(self, user_id: str, note_id: str):
        """
        Delete all sentences belonging to a specific note.

        Args:
            user_id (str): User ID.
            note_id (str): Note ID.
        """
        delete_query = """
        DELETE FROM user_notes
        WHERE user_id = %s AND note_id = %s;
        """
        self.cursor.execute(delete_query, (user_id, note_id))
        logger.debug("Note sentences deleted", extra={"user_id": user_id, "note_id": note_id})

    def get_all_data(self):
        """
        Fetch all entries from user_notes (Warning: Large datasets).

        Returns:
            list: List of row tuples.
        """
        self.cursor.execute(
            "SELECT user_id, note_id, sentence_index, sentence_text, timestamp, date FROM user_notes;"
        )
        return self.cursor.fetchall()

    def delete_sentence(self, user_id: str, note_id: str, sentence_index: int):
        """
        Delete a single specific sentence.

        Args:
            user_id (str): User ID.
            note_id (str): Note ID.
            sentence_index (int): Index of the sentence within the note.
        """
        delete_query = """
        DELETE FROM user_notes
        WHERE user_id = %s AND note_id = %s AND sentence_index = %s;
        """
        self.cursor.execute(delete_query, (user_id, note_id, sentence_index))
        logger.debug(
            "Specific sentence deleted",
            extra={"sentence_index": sentence_index, "user_id": user_id, "note_id": note_id},
        )
