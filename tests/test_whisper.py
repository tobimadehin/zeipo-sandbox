import unittest
import whisper
import torch
import os
import time
import numpy as np

class TestWhisperSetup(unittest.TestCase):
    """Test basic Whisper functionality."""
    
    def test_whisper_import(self):
        """Test that Whisper is correctly imported."""
        self.assertIsNotNone(whisper)
    
    def test_cuda_availability(self):
        """Test CUDA availability."""
        is_available = torch.cuda.is_available()
        if is_available:
            device_name = torch.cuda.get_device_name(0)
            print(f"CUDA is available. Device: {device_name}")
        else:
            print("CUDA is not available. Using CPU.")
        
        # Not a strict test, just informational
        self.assertTrue(True)
    
    def test_model_loading(self):
        """Test loading the tiny model."""
        model = whisper.load_model("tiny")
        self.assertIsNotNone(model)
        print(f"Model loaded on device: {model.device}")
        
        # Check model properties
        self.assertTrue(hasattr(model, "dims"))
        self.assertTrue(hasattr(model, "encoder"))
        self.assertTrue(hasattr(model, "decoder"))
    
    @unittest.skipIf(not os.path.exists("data/samples/english_sample.mp3"), 
                     "Test audio file not found")
    def test_audio_loading(self):
        """Test audio loading functionality."""
        audio_path = "data/samples/english_sample.mp3"
        audio = whisper.load_audio(audio_path)
        
        self.assertIsInstance(audio, np.ndarray)
        self.assertEqual(audio.dtype, np.float32)
        
        # Get audio duration
        duration = len(audio) / whisper.audio.SAMPLE_RATE
        print(f"Audio duration: {duration:.2f} seconds")
    
    @unittest.skipIf(not os.path.exists("data/samples/english_sample.mp3"), 
                     "Test audio file not found")
    def test_basic_transcription(self):
        """Test basic transcription with tiny model."""
        model = whisper.load_model("tiny")
        audio_path = "data/samples/english_sample.mp3"
        
        start_time = time.time()
        result = model.transcribe(audio_path)
        transcribe_time = time.time() - start_time
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn("text", result)
        self.assertIn("segments", result)
        
        # Print transcription details
        print(f"Transcription completed in {transcribe_time:.2f} seconds")
        print(f"Transcribed text: {result['text'][:100]}...")
        print(f"Number of segments: {len(result['segments'])}")

if __name__ == "__main__":
    unittest.main()