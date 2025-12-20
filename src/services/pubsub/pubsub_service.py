"""
Service for interacting with Google Cloud Pub/Sub.
Handles message subscriptions, flow control, and asynchronous message processing.
"""

import json
import threading
from typing import Optional
import google.cloud.pubsub_v1 as pubsub_v1
from google.oauth2 import service_account
from common.utils import get_input_data
from util.util import upstream_call
from services.llm.llm_service import run_smart, run_stt
from config.settings import GCP_PROJECT_ID, PUBSUB_SERVICE_ACCOUNT_PATH
from config.config import User_Input_Type
from common.logging import get_logger

logger = get_logger(__name__)


class PubsubServiceError(Exception):
    """Custom exception for Pub/Sub service errors."""

    pass


class PubSubService:
    """
    Standardized Pub/Sub service implementation.
    Includes flow control, structured logging, and graceful startup/shutdown.
    """

    def __init__(self, subscription_id: str, name: str):
        """
        Initialize the Pub/Sub service instance.

        Args:
            subscription_id (str): The Google Cloud Pub/Sub subscription ID.
            name (str): Identifier for the service instance (e.g., 'stt', 'smart').

        Raises:
            PubSubServiceError: If required configuration is missing.
        """
        if not GCP_PROJECT_ID:
            raise PubsubServiceError("GCP_PROJECT_ID not configured")
        if not PUBSUB_SERVICE_ACCOUNT_PATH:
            raise PubsubServiceError("PUBSUB_SERVICE_ACCOUNT_PATH not configured")
        if not subscription_id:
            raise PubsubServiceError("subscription_id not configured")

        self.credentials = service_account.Credentials.from_service_account_file(
            PUBSUB_SERVICE_ACCOUNT_PATH
        )
        self.subscriber = pubsub_v1.SubscriberClient(credentials=self.credentials)
        self.subscription_path = self.subscriber.subscription_path(GCP_PROJECT_ID, subscription_id)
        self.flow_control = pubsub_v1.types.FlowControl(
            max_messages=10,
            max_bytes=10 * 1024 * 1024,  # 10 MB
        )

        self.lock = threading.Lock()
        self.listener_future: Optional[pubsub_v1.subscriber.futures.StreamingPullFuture] = None
        self.name = name
        logger.debug(
            "PubSubService initialized",
            extra={
                "project_id": GCP_PROJECT_ID,
                "subscription_path": self.subscription_path,
                "max_concurrent": 10,
            },
        )

    def process_message(self, message: pubsub_v1.subscriber.message.Message, source: str):
        """
        Low-level callback for receiving messages.
        Handles raw decoding and acknowledgement logic.

        Args:
            message: Raw Pub/Sub message object.
            source (str): Source identifier for context.
        """
        try:
            raw = message.data.decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "Received non-JSON message",
                    extra={"raw": raw, "message_id": message.message_id},
                )
                payload = {"raw": raw}

            logger.debug(
                "Received Pub/Sub message",
                extra={
                    "message_id": message.message_id,
                    "payload": payload,
                    "attributes": dict(message.attributes or {}),
                    "publish_time": (
                        message.publish_time.isoformat() if message.publish_time else None
                    ),
                },
            )

            self.handle_message(payload, source=source)
            message.ack()
            logger.debug("Message acknowledged", extra={"message_id": message.message_id})
        except Exception as e:
            logger.critical(
                "Error processing pub/sub message",
                extra={"message_id": getattr(message, "message_id", None), "error": str(e)},
                exc_info=True,
            )
            try:
                message.nack()
            except Exception:
                pass

    def handle_message(self, payload: dict, source: str):
        """
        High-level message handler implementing business logic.

        Args:
            payload (dict): Decoded JSON payload from message.
            source (str): Processing branch identifier ('stt' or 'smart').
        """
        data = payload.get("data")
        gcs_audio_url = data.get("gcs_audio_url") if data else None
        input_text = data.get("input_text") if data else None
        note_id = data.get("note_id") if data else None
        user_id = data.get("user_id") if data else None
        location = data.get("location") if data else None
        timestamp = data.get("timestamp") if data else None
        input_type = data.get("input_type") if data else None

        input_data = None
        if input_type == User_Input_Type.AUDIO_WAV:
            if gcs_audio_url is None:
                raise PubsubServiceError("GCS audio url is required for audio input type")
            input_data = get_input_data(gcs_audio_url)

        if input_type == User_Input_Type.TEXT_PLAIN:
            if input_text is None:
                raise PubsubServiceError("Input text is required for text input type")
            input_data = input_text

        logger.debug(
            "Fetched input data",
            extra={"url": gcs_audio_url, "size_bytes": len(input_data) if input_data else 0},
        )

        if source == "stt":
            logger.info("Executing pipeline from Pub/Sub", extra={"branch": "stt"})
            response, metrics = run_stt(input_data)
            logger.info("Pipeline completed from Pub/Sub", extra={"branch": "stt"})
            logger.debug(
                "Pipeline output metrics",
                extra={
                    "branch": "stt",
                    "response_present": response is not None,
                    "metrics_present": metrics is not None,
                },
            )

            upstream_output = {
                "note_id": note_id,
                "user_id": user_id,
                "location": location,
                "timestamp": timestamp,
                "processed_output": response,
                "branch": "stt",
                "metrics": metrics,
            }
            upstream_call(upstream_output)

        elif source == "smart":
            logger.info("Executing pipeline from Pub/Sub", extra={"branch": "smart"})
            response, metrics = run_smart(input_data)
            logger.info("Pipeline completed from Pub/Sub", extra={"branch": "smart"})
            logger.debug(
                "Pipeline output metrics",
                extra={
                    "branch": "smart",
                    "response_present": response is not None,
                    "metrics_present": metrics is not None,
                },
            )

            upstream_output = {
                "note_id": note_id,
                "user_id": user_id,
                "location": location,
                "timestamp": timestamp,
                "processed_output": response,
                "branch": "smart",
                "metrics": metrics,
            }
            upstream_call(upstream_output)

    def start_listener(self):
        """
        Start the Pub/Sub asynchronous message listener.

        Returns:
            StreamingPullFuture: Future object for the subscriber listener.
        """

        def callback_wrapper(message):
            self.process_message(message, source=self.name)

        with self.lock:
            if self.listener_future and not self.listener_future.cancelled():
                logger.info("Listener already running")
                return self.listener_future

            try:
                if not self.subscription_path:
                    raise ValueError("Pub/Sub subscription path is not set.")
                streaming_pull_future = self.subscriber.subscribe(
                    self.subscription_path,
                    callback=callback_wrapper,
                    flow_control=self.flow_control,
                )
                logger.info(
                    "Pub/Sub listener started", extra={"subscription_path": self.subscription_path}
                )
                return streaming_pull_future
            except Exception as e:
                logger.error(
                    "Failed to start Pub/Sub listener",
                    extra={"subscription_path": self.subscription_path, "error": str(e)},
                )
                raise

    def stop_listener(self, streaming_pull_future):
        """
        Stop the Pub/Sub subscriber listener gracefully.

        Args:
            streaming_pull_future: The future returned by start_listener.
        """
        try:
            streaming_pull_future.cancel()
            logger.info("Pub/Sub listener stopped")
        except Exception as e:
            logger.error("Failed to stop Pub/Sub listener", extra={"error": str(e)})
            raise
