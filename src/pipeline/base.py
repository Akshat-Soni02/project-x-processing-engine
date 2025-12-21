"""
Abstract base class for all processing pipelines.
Enforces a standard structure for execution, error handling, and upstream communication.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from common.logging import get_logger
from pipeline.exceptions import FatalPipelineError, TransientPipelineError
from util.util import upstream_call


class Pipeline(ABC):
    """
    Abstract base class for processing pipelines.
    Subclasses must implement the _process method.
    """

    def __init__(self, name: str):
        """
        Initialize the pipeline.

        Args:
            name (str): Name of the pipeline (e.g., "stt", "smart").
        """
        self.name = name
        self.logger = get_logger(f"pipeline.{name}")

    def run(self, input_data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute the pipeline with standardized error handling and upstream reporting.

        Args:
            input_data (Any): Input data for the pipeline.
            context (Dict[str, Any], optional): Additional context (e.g., user_id, note_id).

        Returns:
            Dict[str, Any]: The upstream payload that was sent.
        """
        context = context or {}
        user_id = context.get("user_id")
        note_id = context.get("note_id")

        self.logger.info(
            "Starting pipeline execution",
            extra={"pipeline": self.name, "user_id": user_id, "note_id": note_id},
        )

        response = None
        metrics = None
        error_info = None

        try:
            # Execute core logic implemented by subclasses
            response, metrics = self._process(input_data, context)

            if response is None:
                self.logger.warning("Pipeline returned empty response")

            self.logger.info(
                "Pipeline execution completed successfully",
                extra={"pipeline": self.name, "user_id": user_id},
            )

        except FatalPipelineError as e:
            self.logger.critical(
                "Fatal pipeline error",
                extra={"error": str(e), "pipeline": self.name},
                exc_info=True,
            )
            error_info = {"type": "fatal", "message": str(e)}

        except TransientPipelineError as e:
            self.logger.error(
                "Transient pipeline error",
                extra={"error": str(e), "pipeline": self.name},
                exc_info=True,
            )
            error_info = {"type": "transient", "message": str(e)}

        except Exception as e:
            self.logger.critical(
                "Unhandled exception in pipeline",
                extra={"error": str(e), "pipeline": self.name},
                exc_info=True,
            )
            error_info = {"type": "unhandled", "message": str(e)}

        # Construct upstream payload
        upstream_payload = {
            "note_id": note_id,
            "user_id": user_id,
            "location": context.get("location"),
            "timestamp": context.get("timestamp"),
            "processed_output": response,
            "branch": self.name,
            "metrics": metrics,
            "error": error_info,
        }

        # Final callback to upstream
        self._send_upstream(upstream_payload)

        return upstream_payload

    @abstractmethod
    def _process(
        self, input_data: Any, context: Dict[str, Any]
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Core processing logic to be implemented by subclasses.

        Args:
            input_data (Any): Validated input data.
            context (Dict[str, Any]): Context metadata.

        Returns:
            Tuple[Optional[Dict], Optional[Dict]]: (response_data, metrics_data)
        """
        pass

    def _send_upstream(self, payload: Dict[str, Any]):
        """
        Send the final result to the upstream service.
        """
        try:
            upstream_call(payload)
        except Exception as e:
            # upstream_call already logs errors, but we catch here to ensure run() doesn't crash
            self.logger.error("Failed to send upstream", extra={"error": str(e)})
