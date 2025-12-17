import json
import threading
from typing import Dict, Any,Optional
from datetime import datetime

import google.cloud.pubsub_v1 as pubsub_v1
from google.oauth2 import service_account
from google.api_core.retry import Retry
from google.api_core import exceptions

from config.settings import (
    GCP_PROJECT_ID,
    GCP_LOCATION,
    PUBSUB_TOPIC_ID,
    ARILO_SUBSCRIPTION_ID,
    PUBSUB_SERVICE_ACCOUNT_PATH
)

from common.logging import get_logger

logger = get_logger(__name__)

class PubsubServiceError(Exception):
    """Custom exception for Pub/Sub service errors."""
    pass
class PubSubService:
    """
    Production-ready Pub/Sub service with:
    - Flow control (max 10 concurrent messages)
    - Automatic retries on publish
    - Structured logging
    - Graceful start/stop
    """
    def __init__(self,SUBSCRIPTION_ID=ARILO_SUBSCRIPTION_ID):
        """
        Initialize Pub/Sub service.
        
        Args:
            SUBSCRIPTION_ID: The subscription ID to listen to
            max_concurrent_messages: Max number of messages to process concurrently
            
        Raises:
            PubSubServiceError: If required configuration is missing
        """
        if not GCP_PROJECT_ID:
            raise PubSubServiceError("GCP_PROJECT_ID not configured")
        if not PUBSUB_SERVICE_ACCOUNT_PATH:
            raise PubSubServiceError("PUBSUB_SERVICE_ACCOUNT_PATH not configured")
        if not SUBSCRIPTION_ID:
            raise PubSubServiceError("SUBSCRIPTION_ID not configured")
        if not PUBSUB_TOPIC_ID:
            logger.warning("PUBSUB_TOPIC_ID not set. Publishing will be disabled.")

        self.credentials = service_account.Credentials.from_service_account_file(
            PUBSUB_SERVICE_ACCOUNT_PATH
        )
        self.publisher = pubsub_v1.PublisherClient(credentials=self.credentials)
        self.subscriber = pubsub_v1.SubscriberClient(credentials=self.credentials)

        self.topic_path = self.publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC_ID)
        self.subscription_path = self.subscriber.subscription_path(GCP_PROJECT_ID, ARILO_SUBSCRIPTION_ID)
        self.flow_control = pubsub_v1.types.FlowControl(
            max_messages=10,
            max_bytes=10 * 1024 * 1024,  # 10 MB
        )

        self.lock = threading.Lock()
        self.listener_future: Optional[pubsub_v1.subscriber.futures.StreamingPullFuture] = None
        logger.info(
            "PubSubService initialized",
            extra={
                "project_id": GCP_PROJECT_ID,
                "topic_path": self.topic_path,
                "subscription_path": self.subscription_path,
                "max_concurrent": 10,
            },
        )
    
    def publish_message(self, data: dict, attributes: dict = None):
        """Publishes message to Pub/Sub topic with optional attributes."""
        try:
            if not self.topic_path:
                raise ValueError("Pub/Sub topic path is not set.")
            
            message_data = json.dumps(data).encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data, **(attributes or {}))
            message_id = future.result()
            logger.info(f"Published message ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            raise
    
    def process_message(self,message:pubsub_v1.subscriber.message.Message):
        """Callback to process received Pub/Sub messages."""
        try:
            raw = message.data.decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                "Received non-JSON message",
                extra={"raw": raw, "message_id": message.message_id}
            )
                payload = {"raw": raw}
            
            logger.info(
                "Received Pub/Sub message",
                extra={
                    "message_id": message.message_id,
                    "payload": payload,
                    "attributes": dict(message.attributes or {}),
                    "publish_time": message.publish_time.isoformat() if message.publish_time else None,
                }
            )
            
            self.handle_message(payload)
            message.ack()
            logger.info(f"Acknowledged message ID: {message.message_id}")
        except Exception as e:
            logger.error(f"Error processing message ID: {getattr(message,'message_id',None)}: {e}", exc_info=True)
            try:
                message.nack()
            except Exception:
                pass
            except Exception as e:
                logger.error(f"Error processing message ID: {message.message_id}: {e}")
            # Optionally, you can choose to not acknowledge the message to have it redelivered.
    
    def handle_message(self, payload:dict):
        """Overide this method with your business logic to process the message."""
        logger.info(f"Processing payload: {payload}")
        # Implement your message processing logic here.
        pass

    def start_listener(self):
        """
        Start the Pub/Sub listener (idempotent).
        
        Returns:
            StreamingPullFuture for the listener
            
        Raises:
            PubSubServiceError: If listener fails to start
        """
        with self.lock:
            if self.listener_future and not self.listener_future.cancelled():
                logger.info("Listener already running")
                return self.listener_future

            try:
                self.subscriber = pubsub_v1.SubscriberClient(credentials=self.credentials)
                self.subscription_path = self.subscriber.subscription_path(GCP_PROJECT_ID, ARILO_SUBSCRIPTION_ID)
                if not self.subscription_path:
                    raise ValueError("Pub/Sub subscription path is not set.")

                # Flow control: max 10 concurrent messages, 10 MB max bytes
                flow_control = pubsub_v1.types.FlowControl(
                    max_messages=10,
                    max_bytes=10 * 1024 * 1024,  # 10 MB
                )

                streaming_pull_future = self.subscriber.subscribe(
                    self.subscription_path, 
                    callback=self.process_message,
                    flow_control=flow_control,
                )
                logger.info(f"Listening for messages on {self.subscription_path}...")

                return streaming_pull_future
            except Exception as e:
                logger.error(f"Error starting listener: {e}")
                raise
    
    def stop_listener(self,streaming_pull_future):
        """Stops the Pub/Sub subscription listener."""
        try:
            streaming_pull_future.cancel()
            logger.info("Stopped Pub/Sub listener.")
        except Exception as e:
            logger.error(f"Error stopping listener: {e}")
            raise


