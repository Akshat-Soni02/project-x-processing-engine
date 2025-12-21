"""
Abstract base class for all processing pipelines.
Enforces a standard structure for execution, error handling, and upstream communication.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from common.logging import get_logger
from pipeline.exceptions import FatalPipelineError, TransientPipelineError
from util.util import upstream_call
from db.db import Database
from config.config import Pipeline_Stage_Status, Llm_Call


class Pipeline(ABC):
    """
    Abstract base class for processing pipelines.
    Subclasses must implement the _process method.
    """

    def __init__(self, name: str, db: Database):
        """
        Initialize the pipeline.

        Args:
            name (str): Name of the pipeline (e.g., "stt", "smart").
        """
        self.name = name
        self.logger = get_logger(f"pipeline.{name}")
        self.db = db

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
        job_id = context.get("job_id")
        pipeline_stage_id = context.get("pipeline_stage_id")
        user_id = context.get("user_id")
        note_id = context.get("note_id")

        self.logger.info(
            "Starting pipeline execution",
            extra={
                "pipeline": self.name,
                "user_id": user_id,
                "note_id": note_id,
                "pipeline_stage_id": pipeline_stage_id,
            },
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
                extra={
                    "pipeline": self.name,
                    "user_id": user_id,
                    "note_id": note_id,
                    "pipeline_stage_id": pipeline_stage_id,
                },
            )

        except (FatalPipelineError, TransientPipelineError):
            raise
        except Exception as e:
            self.logger.critical(
                "Unhandled exception in pipeline",
                extra={
                    "error": str(e),
                    "pipeline": self.name,
                    "pipeline_stage_id": pipeline_stage_id,
                },
                exc_info=True,
            )
            raise TransientPipelineError("Unhandled exception in pipeline", original_error=e)

        # if successfull then
        # insert output, update status to completed, increment attempt count

        try:
            self.db.write_pipeline_stage_output(pipeline_stage_id, response)
            self.db.update_pipeline_stage_status(
                pipeline_stage_id, Pipeline_Stage_Status.COMPLETED.value
            )
        except Exception as e:
            self.logger.error("Failed to update stage status", extra={"error": str(e)})
            raise TransientPipelineError("Failed to update stage status", original_error=e)

        # Construct upstream payload
        upstream_payload = {
            "job_id": job_id,
            "note_id": note_id,
            "user_id": user_id,
            "location": context.get("location"),
            "timestamp": context.get("timestamp"),
            "output": response,
            "input_type": context.get("input_type"),
            "pipeline_stage": self.name,
            "status": Pipeline_Stage_Status.COMPLETED.value,
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

    def _write_metrics(self, pipeline_stage_id: str, llm_call: Llm_Call, metrics: Dict[str, Any]):
        """
        Write metrics to the database.
        """
        try:
            self.db.write_metrics(pipeline_stage_id, llm_call, metrics)
        except Exception as e:
            self.logger.error("Failed to write metrics", extra={"error": str(e)})
