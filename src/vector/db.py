import psycopg
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from common.logging import get_logger
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

logger = get_logger(__name__)


# TODO migrate the module from vertexai.language_models to google-genai as its depricating
class Database:
    def __init__(self):
        """Initialize database connection."""
        self.conn = psycopg.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()
        logger.info("Database connection established.")

        self.embedding_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
        self.embedding_dimensionality = 1536

    def __del__(self):
        """Close database connection."""
        self.cursor.close()
        self.conn.close()
        logger.info("Database connection closed.")

    def _generate_query_embedding(self, text: str) -> list[float]:
        """Generate embedding for the given text using an embedding model."""

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
        char_count = len(text)
        return embedding_response[0].values, char_count

    def _generate_sentence_embedding(self, sentence: str) -> list[float]:
        """Generate embedding for a sentence using an embedding model."""

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
        char_count = len(sentence)
        return embedding_response[0].values, char_count

    # based on current Arch, this does not belong here
    def insert_sentences(self, user_id: str, note_id: str, sentences: list[dict]):
        """Insert sentences with embeddings into the database"""

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
        logger.info(
            f"Inserted {len(sentences)} sentences for user_id={user_id}, note_id={note_id}."
        )
        return total_chars

    def similarity_search(self, user_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Perform multi-factor similarity search considering similarity, importance, and recency."""
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
            (rn.importance_score / s.max_importance) * 0.2 +
            ((rn.ts_epoch - s.min_ts) / (s.max_ts - s.min_ts)) * 0.2 AS combined_score
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
        logger.info(
            f"Performed multi-factor similarity search for user_id={user_id} with query='{query}'."
        )
        return similar_sentences, query_chars

    def get_sentence(self, filter) -> dict:
        user_id = filter.get("user_id", None)
        note_id = filter.get("note_id", None)
        sentence_index = filter.get("sentence_index", None)

        search_part = ""

        if note_id is not None:
            search_part += "AND note_id = %s "
        if sentence_index is not None:
            search_part += "AND sentence_index = %s "

        select_query = (
            """
        SELECT sentence_index, sentence_text, importance_score
        FROM user_notes
        WHERE user_id = %s """
            + search_part
            + ";"
        )

        params = [user_id]
        if note_id is not None:
            params.append(note_id)
        if sentence_index is not None:
            params.append(sentence_index)

        self.cursor.execute(select_query, tuple(params))
        result = self.cursor.fetchone()

        if result:
            sentence_index, sentence_text, importance_score = result
            return {
                "sentence_index": sentence_index,
                "sentence_text": sentence_text,
                "importance_score": importance_score,
            }
        else:
            return None

    def delete_sentences(self, user_id: str, note_id: str):
        """Delete sentences for a given user_id and note_id."""
        delete_query = """
        DELETE FROM user_notes
        WHERE user_id = %s AND note_id = %s;
        """
        self.cursor.execute(delete_query, (user_id, note_id))
        logger.info(f"Deleted sentences for user_id={user_id}, note_id={note_id}.")

    def get_all_data(self):
        """Retrieve all data from the user_notes table."""
        self.cursor.execute(
            "SELECT user_id, note_id, sentence_index, sentence_text, timestamp, date FROM user_notes;"
        )
        return self.cursor.fetchall()

    def delete_sentence(self, user_id: str, note_id: str, sentence_index: int):
        """Delete a specific sentence for a given user_id, note_id, and sentence_index."""
        delete_query = """
        DELETE FROM user_notes
        WHERE user_id = %s AND note_id = %s AND sentence_index = %s;
        """
        self.cursor.execute(delete_query, (user_id, note_id, sentence_index))
        logger.info(
            f"Deleted sentence_index={sentence_index} for user_id={user_id}, note_id={note_id}."
        )
