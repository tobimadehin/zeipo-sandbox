import unittest
import numpy as np
import time
import os
import whisper
from src.streaming.whisper_streaming import WhisperStreamingTranscriber

class TestWhisperStreaming(unittest.TestCase):
    """Test the WhisperStreamingTranscriber class."""
    
    @unittest.skipIf(not os.path.exists("data/samples/english_sample.mp3"), 
                     "Test audio file not found")
    def test_streaming_transcription(self):
        """Test streaming transcription by simulating chunks."""
        # Load test audio
        audio_path = "data/samples/english_sample.mp3"
        audio = whisper.load_audio(audio_path)
        
        # Create streaming transcriber with tiny model for speed
        transcriber = WhisperStreamingTranscriber(
            model_name="tiny",
            chunk_size_ms=1000,
            buffer_size_ms=5000
        )
        
        # Callback to collect results
        results = []
        def callback(result):
            results.append(result)
            print(f"Received update: {result['text'][:50]}...")
        
        # Start transcription
        transcriber.start(callback)
        
        # Calculate chunk size in samples
        chunk_samples = transcriber.chunk_samples
        
        # Simulate streaming by sending chunks
        for i in range(0, len(audio), chunk_samples):
            # Get chunk
            chunk = audio[i:i+chunk_samples]
            
            # Add to transcriber
            transcriber.add_audio_chunk(chunk)
            
            # Small sleep to simulate real-time processing
            time.sleep(0.1)
        
        # Get final results
        final_result = transcriber.stop()
        
        # Verify results
        self.assertIsInstance(final_result, dict)
        self.assertIn("text", final_result)
        self.assertIn("segments", final_result)
        
        # Check if we got any callbacks
        self.assertGreater(len(results), 0)
        
        print(f"Final transcription: {final_result['text'][:100]}...")
        print(f"Received {len(results)} streaming updates")

if __name__ == "__main__":
    unittest.main()