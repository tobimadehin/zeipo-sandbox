# src/stt/stt_base.py
import whisper
import torch
import numpy as np
from typing import Dict, Optional, Callable
import threading
import queue
import time
from static.constants import logger

class STTProvider:
    """
    A class to handle streaming transcription with Whisper.
    """
    def __init__(
        self,
        model_name: str = "small",
        language: Optional[str] = None,
        chunk_size_ms: int = 1000,
        buffer_size_ms: int = 5000,
        device: Optional[str] = None,
    ):
        """
        Initialize the streaming transcriber.
        
        Args:
            model_name: Whisper model size to use
            language: Language code if known, otherwise language detection is used
            chunk_size_ms: Size of audio chunks to process in milliseconds
            buffer_size_ms: Size of the buffer window in milliseconds
            device: Device to run inference on ('cuda' or 'cpu')
        """
        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        logger.info(f"Using device: {self.device}")
        
        # Load model
        logger.info(f"Loading {model_name} model...")
        self.model = whisper.load_model(model_name, device=self.device)
        logger.info(f"Model loaded successfully.")
        
        # Configuration
        self.language = language
        self.chunk_size_ms = chunk_size_ms
        self.buffer_size_ms = buffer_size_ms
        self.sample_rate = whisper.audio.SAMPLE_RATE  # 16000 Hz
        self.chunk_samples = self.sample_rate * chunk_size_ms // 1000
        self.buffer_samples = self.sample_rate * buffer_size_ms // 1000
        
        # State
        self.audio_buffer = np.array([], dtype=np.float32)
        self.processed_chunks = 0
        self.is_running = False
        self.callback_fn = None
        self.audio_queue = queue.Queue()
        self.process_thread = None
        
        # Results
        self.transcript = ""
        self.segments = []
    
    def add_audio_chunk(self, audio_chunk: np.ndarray) -> None:
        """
        Add an audio chunk to the processing queue.
        """
        if self.is_running:
            self.audio_queue.put(audio_chunk)
    
    def start(self, callback_fn: Optional[Callable] = None) -> None:
        """
        Start the streaming transcription.
        
        Args:
            callback_fn: Function to call with intermediate results
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.callback_fn = callback_fn
        self.process_thread = threading.Thread(target=self._process_stream)
        self.process_thread.daemon = True
        self.process_thread.start()
        logger.info("Streaming transcription started")
    
    def stop(self) -> Dict:
        """
        Stop the streaming transcription and return final results.
        """
        if not self.is_running:
            return {"text": self.transcript, "segments": self.segments}
        
        self.is_running = False
        
        # Process any remaining audio in the buffer
        if len(self.audio_buffer) > 0:
            try:
                result = self.model.transcribe(
                    self.audio_buffer, 
                    language=self.language,
                    fp16=False
                )
                self.transcript = result["text"]
                self.segments = result["segments"]
            except Exception as e:
                logger.error(f"Error in final transcription: {str(e)}")
        
        logger.info("Streaming transcription stopped")
        return {"text": self.transcript, "segments": self.segments}
    
    def _process_stream(self) -> None:
        """
        Background thread for processing audio chunks.
        """
        while self.is_running:
            try:
                # Get audio chunk from queue with timeout
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Add to buffer
                self.audio_buffer = np.append(self.audio_buffer, audio_chunk)
                
                # Calculate buffer duration
                buffer_duration = len(self.audio_buffer) / self.sample_rate
                
                # Only process when we have at least 2 seconds of audio and every 3rd chunk
                if buffer_duration >= 2.0 and self.processed_chunks % 3 == 0:
                    try:
                        # Process the audio buffer
                        result = self.model.transcribe(
                            self.audio_buffer, 
                            language=self.language,
                            fp16=False
                        )
                        
                        # Update transcript
                        self.transcript = result["text"]
                        self.segments = result["segments"]
                        
                        # Call callback if provided
                        if self.callback_fn:
                            self.callback_fn({
                                "text": self.transcript,
                                "segments": self.segments,
                                "is_final": False
                            })
                        
                        self.processed_chunks += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing chunk: {str(e)}", exc_info=True)
                
                self.processed_chunks += 1
            
                # Trim buffer if too large, but keep more context than before
                max_buffer_duration = 10.0  # 10 seconds max buffer (increased from 5s)
                max_buffer_samples = int(max_buffer_duration * self.sample_rate)
                if len(self.audio_buffer) > max_buffer_samples:
                    # Keep the most recent audio
                    self.audio_buffer = self.audio_buffer[-max_buffer_samples:]
                    
                # Mark task as done
                self.audio_queue.task_done()
                
                logger.debug(f"Processed {self.processed_chunks} chunks of size {len(self.audio_buffer)} from buffer")
                
            except Exception as e:
                logger.error(f"Error in streaming process: {str(e)}", exc_info=True)
                if self.is_running:
                    time.sleep(0.1)  # Prevent tight loop on error
        
        logger.info("Processing thread stopped")