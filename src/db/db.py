"""
Vector database interface for storing and searching note embeddings.
Uses PostgreSQL with pgvector for efficient similarity search and context retrieval.
"""

import psycopg
import uuid
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
        try:
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
        except psycopg.errors.UndefinedColumn as e:
            logger.critical("Schema mismatch: %s", e)
            raise

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

    # def insert_sentences(self, user_id: str, note_id: str, sentences: list[dict]) -> int:
    #     """
    #     Insert multiple sentences with their embeddings into the database.

    #     Args:
    #         user_id (str): ID of the user owning the note.
    #         note_id (str): ID of the note.
    #         sentences (list[dict]): List of dictionaries containing sentence text and metadata.

    #     Returns:
    #         int: Total characters processed for billing/tracking purposes.
    #     """
    #     insert_query = """
    #     INSERT INTO user_notes (user_id, note_id, sentence_index, sentence_text, embedding, language, importance_score)
    #     VALUES (%s, %s, %s, %s, %s, %s, %s)
    #     ON CONFLICT (user_id, note_id, sentence_index) DO NOTHING;
    #     """
    #     total_chars = 0
    #     for sentence in sentences:
    #         sentence_index = sentence["sentence_index"]
    #         sentence_text = sentence["sentence_text"]
    #         language = sentence.get("language", "en")
    #         embedding, char_count = self._generate_sentence_embedding(sentence_text)
    #         total_chars += char_count
    #         importance_score = sentence.get("importance_score", 0)
    #         self.cursor.execute(
    #             insert_query,
    #             (
    #                 user_id,
    #                 note_id,
    #                 sentence_index,
    #                 sentence_text,
    #                 embedding,
    #                 language,
    #                 importance_score,
    #             ),
    #         )
    #     logger.debug(
    #         "Sentences inserted into database",
    #         extra={"count": len(sentences), "user_id": user_id, "note_id": note_id},
    #     )
    #     return total_chars

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

    # Table llm_metrics {
    # id uuid [pk]
    # job_id uuid [not null]
    # audio_id uuid [not null]
    # pipeline_stage_id uuid [not null]
    # llm_call enum('STT', 'CONTEXT', 'NOTEBACK')
    # input_tokens int
    # prompt_tokens int
    # total_input_tokens int
    # output_tokens int
    # thought_tokens int
    # confidence_score float
    # elapsed_time float
    # }

    # Table pipeline_stages {
    # id uuid [pk]

    # job_id uuid [not null]
    # pipeline_name enum

    # status enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')

    # attempt_count int [default: 0]
    # last_heartbeat timestamp
    # error_message text

    # started_at timestamp
    # completed_at timestamp

    # indexes {
    #     (job_id, pipeline_name) [unique]
    # }

    # }

    # Table pipeline_outputs {
    #   id uuid [pk]

    #   pipeline_stage_id uuid [not null]

    #   content text
    #   data jsonb

    #   start_second int
    #   end_second int

    #   created_at timestamp
    #   deleted_at timestamp
    # }

    def write_metrics(self, metrics: dict):
        """
        Write metrics to the database.

        Args:
            metrics (dict): Dictionary containing metrics to be written.
        """
        insert_query = """
        INSERT INTO llm_metrics (job_id, audio_id, pipeline_stage_id, llm_call, input_tokens, prompt_tokens, total_input_tokens, output_tokens, thought_tokens, confidence_score, elapsed_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        self.cursor.execute(insert_query, tuple(metrics.values()))
        self.conn.commit()

    def read_stage(self, job_id: uuid, pipeline_name: str) -> dict:
        """
        Read stage from the database.

        Args:
            job_id (uuid): ID of the job to be read.
            pipeline_name (str): Name of the pipeline to be read.

        Returns:
            dict: Dictionary containing stage information.
        """
        select_query = """
        SELECT * FROM pipeline_stages WHERE job_id = %s AND pipeline_name = %s;
        """
        self.cursor.execute(select_query, (job_id, pipeline_name))
        result = self.cursor.fetchone()
        if result:
            return {
                "job_id": result[0],
                "pipeline_name": result[1],
                "status": result[2],
                "attempt_count": result[3],
                "last_heartbeat": result[4],
                "error_message": result[5],
                "started_at": result[6],
                "completed_at": result[7],
            }
        return None

    def read_output(self, pipeline_stage_id: uuid) -> dict:
        """
        Read pipeline output from the database.

        Args:
            pipeline_stage_id (uuid): ID of the pipeline stage to be read.

        Returns:
            dict: Dictionary containing output information.
        """
        select_query = """
        SELECT * FROM pipeline_outputs WHERE pipeline_stage_id = %s;
        """
        self.cursor.execute(select_query, (pipeline_stage_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                "pipeline_stage_id": result[0],
                "content": result[1],
                "data": result[2],
                "start_second": result[3],
                "end_second": result[4],
                "created_at": result[5],
                "deleted_at": result[6],
            }
        return None

    def update_pipeline_stage_status(self, pipeline_stage_id: uuid, status: str):
        """
        Update pipeline stage status in the database.

        Args:
            pipeline_stage_id (uuid): ID of the pipeline stage to be updated.
            status (str): New status of the pipeline stage.
        """
        update_query = """
        UPDATE pipeline_stages SET status = %s WHERE id = %s;
        """
        self.cursor.execute(update_query, (status, pipeline_stage_id))
        self.conn.commit()

    def update_pipeline_stage_error(self, pipeline_stage_id: uuid, error_message: str):
        """
        Update pipeline stage error in the database.

        Args:
            pipeline_stage_id (uuid): ID of the pipeline stage to be updated.
            error_message (str): New error message of the pipeline stage.
        """
        update_query = """
        UPDATE pipeline_stages SET error_message = %s WHERE id = %s;
        """
        self.cursor.execute(update_query, (error_message, pipeline_stage_id))
        self.conn.commit()

    def write_pipeline_output(self, pipeline_stage_id: uuid, output: dict):
        """
        Write pipeline output to the database.

        Args:
            pipeline_stage_id (uuid): ID of the pipeline stage to be written.
            output (dict): Dictionary containing output information.
        """
        insert_query = """
        INSERT INTO pipeline_outputs (pipeline_stage_id, content, data, start_second, end_second)
        VALUES (%s, %s, %s, %s, %s);
        """
        self.cursor.execute(insert_query, tuple(pipeline_stage_id, output.values()))
        self.conn.commit()

    # def read_job(self, job_id: str) -> list[dict]:
    #     """
    #     Read job from the database.

    #     Args:
    #         job_id (str): ID of the job to be read.

    #     Returns:
    #         list: List of job dictionaries.
    #     """
    #     select_query = """
    #     SELECT * FROM jobs WHERE job_id = %s;
    #     """
    #     self.cursor.execute(select_query, (job_id,))
    #     result = self.cursor.fetchone()
    #     if result:
    #         return {
    #             "job_id": result[0],
    #             "user_id": result[1],
    #             "audio_id": result[2],
    #             "status": result[3],
    #             "error_code": result[4],
    #             "error_message": result[5],
    #             "retry_count": result[6],
    #             "created_at": result[7],
    #             "updated_at": result[8],
    #         }
    #     return None

    # def get_sentence(self, filter_params: dict) -> dict:
    #     """
    #     Retrieve a specific sentence or set of sentences based on filters.

    #     Args:
    #         filter_params (dict): Filters (user_id Required, note_id, sentence_index).

    #     Returns:
    #         dict: The first matching sentence or None.
    #     """
    #     user_id = filter_params.get("user_id")
    #     note_id = filter_params.get("note_id")
    #     sentence_index = filter_params.get("sentence_index")

    #     search_part = ""
    #     params = [user_id]

    #     if note_id is not None:
    #         search_part += "AND note_id = %s "
    #         params.append(note_id)
    #     if sentence_index is not None:
    #         search_part += "AND sentence_index = %s "
    #         params.append(sentence_index)

    #     select_query = f"""
    #     SELECT sentence_index, sentence_text, importance_score
    #     FROM user_notes
    #     WHERE user_id = %s {search_part};
    #     """

    #     self.cursor.execute(select_query, tuple(params))
    #     result = self.cursor.fetchone()

    #     if result:
    #         idx, text, score = result
    #         return {
    #             "sentence_index": idx,
    #             "sentence_text": text,
    #             "importance_score": score,
    #         }
    #     return None

    # def delete_sentences(self, user_id: str, note_id: str):
    #     """
    #     Delete all sentences belonging to a specific note.

    #     Args:
    #         user_id (str): User ID.
    #         note_id (str): Note ID.
    #     """
    #     delete_query = """
    #     DELETE FROM user_notes
    #     WHERE user_id = %s AND note_id = %s;
    #     """
    #     self.cursor.execute(delete_query, (user_id, note_id))
    #     logger.debug("Note sentences deleted", extra={"user_id": user_id, "note_id": note_id})

    # def get_all_data(self):
    #     """
    #     Fetch all entries from user_notes (Warning: Large datasets).

    #     Returns:
    #         list: List of row tuples.
    #     """
    #     self.cursor.execute(
    #         "SELECT user_id, note_id, sentence_index, sentence_text, timestamp, date FROM user_notes;"
    #     )
    #     return self.cursor.fetchall()

    # def delete_sentence(self, user_id: str, note_id: str, sentence_index: int):
    #     """
    #     Delete a single specific sentence.

    #     Args:
    #         user_id (str): User ID.
    #         note_id (str): Note ID.
    #         sentence_index (int): Index of the sentence within the note.
    #     """
    #     delete_query = """
    #     DELETE FROM user_notes
    #     WHERE user_id = %s AND note_id = %s AND sentence_index = %s;
    #     """
    #     self.cursor.execute(delete_query, (user_id, note_id, sentence_index))
    #     logger.debug(
    #         "Specific sentence deleted",
    #         extra={"sentence_index": sentence_index, "user_id": user_id, "note_id": note_id},
    #     )
