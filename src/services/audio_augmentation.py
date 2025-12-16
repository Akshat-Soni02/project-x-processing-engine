# # Audio Augmentation Service
# # This module provides stateless audio augmentation functionalities, including silence removal.

# import io
# import time
# from common.logging import get_logger
# from typing import Dict, Optional, Tuple, Callable, List

# logger = get_logger(__name__)

# try:
#     from pydub import AudioSegment
#     from pydub.silence import split_on_silence
# except ImportError:
#     raise ImportError("pydub not installed. Install with: pip install pydub")


# class AudioProcessingError(Exception):
#     """Custom exception for errors during audio processing."""

#     pass


# class AudioAugmentation:
#     """
#     Stateless processor for applying audio augmentation steps via a pipeline.
#     """

#     def __init__(self, config: Dict):
#         """
#         Initializes the processor with environment parameters.
#         :param config: Dictionary containing all processing parameters.
#         """
#         self.config = config

#         # Silence Processing Parameters
#         self.min_silence_len = config.get("min_silence_len", 1300)  # Default 1300ms
#         self.silence_thresh = config.get("silence_thresh", -42)  # Default -42 dBFS
#         self.keep_silence = config.get("keep_silence", 300)  # Default 300ms
#         self.input_format = config.get("input_format", "wav")  # Default 'wav'
#         self.output_format = config.get("output_format", "wav")  # Default 'wav'

#         # processing pipeline definition
#         self.pipeline: List[Callable[[bytes], Tuple[Optional[bytes], Dict]]] = [
#             self.silence_processing,
#             # self.background_noise_processing, # This would be added here
#         ]

#     def silence_processing(self, audio_bytes: bytes) -> Tuple[Optional[bytes], Dict]:
#         """
#         Removes silent segments

#         Returns:
#             Tuple[Optional[bytes], Dict]: (processed_audio_bytes, metrics)
#         """
#         metrics = {}
#         start_time = time.time()

#         logger.debug(
#             f"Silence params: thresh={self.silence_thresh}dBFS, min_len={self.min_silence_len}ms, keep={self.keep_silence}ms"
#         )

#         try:
#             audio_segment = AudioSegment.from_file(
#                 file=io.BytesIO(audio_bytes), format=self.input_format
#             )

#             # Get original duration (Baseline Metric)
#             original_duration_sec = audio_segment.duration_seconds
#             metrics["original_duration_sec"] = original_duration_sec
#             logger.info(f"Loaded audio for silence removal. Duration: {original_duration_sec:.2f}s")

#             # Split the audio on silent segments (Core Logic)
#             audio_chunks = split_on_silence(
#                 audio_segment,
#                 min_silence_len=self.min_silence_len,
#                 silence_thresh=self.silence_thresh,
#                 keep_silence=self.keep_silence,
#             )

#             # Concatenate the non-empty audio chunks
#             cleaned_audio_segment = AudioSegment.empty()
#             for chunk in audio_chunks:
#                 cleaned_audio_segment += chunk

#             # cleaned duration
#             cleaned_duration_sec = cleaned_audio_segment.duration_seconds
#             metrics["cleaned_duration_sec"] = cleaned_duration_sec
#             metrics["time_removed_sec"] = original_duration_sec - cleaned_duration_sec

#             # Export the cleaned audio to a bytes object
#             in_memory_wav = io.BytesIO()
#             cleaned_audio_segment.export(out_f=in_memory_wav, format=self.output_format)
#             cleaned_audio_bytes = in_memory_wav.getvalue()

#             # performance metric
#             duration = time.time() - start_time
#             metrics["silence_processing_time_sec"] = duration
#             logger.info(
#                 f"Silence removal done in {duration:.4f}s. Removed {metrics['time_removed_sec']:.2f}s."
#             )

#             return cleaned_audio_bytes, metrics

#         except Exception as e:
#             logger.error(f"FATAL: Error during pydub silence processing: {e}", exc_info=True)
#             # In our pipeline, returning None often signals a failure that should stop the process
#             return None, metrics

#     def run_pipeline(self, audio_bytes: bytes) -> bytes:
#         """Runs the audio through the defined pipeline."""
#         current_audio = audio_bytes

#         # Empty metadata dictionary to track processing stats
#         metadata = {}

#         for step_function in self.pipeline:
#             # Each step returns the processed bytes AND metrics/metadata
#             current_audio, step_metadata = step_function(current_audio)

#             if current_audio is None:
#                 logger.error(f"Pipeline failed at step: {step_function.__name__}")
#                 raise AudioProcessingError(f"Processing failed at {step_function.__name__}")

#             metadata.update(step_metadata)

#         logger.info(f"Pipeline completed. Final Metrics: {metadata}")
#         return current_audio
