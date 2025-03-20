# tests/test_tts.py
import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import json
from io import BytesIO

# Import the TTS components to test
from src.tts import get_tts_provider
from src.tts.tts_base import TTSProvider
from src.tts.integrations.google_tts import GoogleTTSProvider
from src.tts.audio_cache import TTSAudioCache
from src.tts.voice_profiles import get_voice_for_language, AFRICAN_VOICE_PROFILES
from config import settings

class TestGoogleTTS(unittest.TestCase):
    """Test the Google TTS functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temp directory for cache testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock the Google TTS client
        self.tts_client_patcher = patch('src.tts.google_tts.texttospeech.TextToSpeechClient')
        self.mock_tts_client = self.tts_client_patcher.start()
        
        # Mock response
        self.mock_response = MagicMock()
        self.mock_response.audio_content = b'test_audio_content'
        self.mock_tts_client.return_value.synthesize_speech.return_value = self.mock_response
        
        # Mock list voices response
        self.mock_voices_response = MagicMock()
        mock_voice = MagicMock()
        mock_voice.name = "en-US-Neural2-F"
        mock_voice.language_codes = ["en-US"]
        mock_voice.ssml_gender = "FEMALE"
        mock_voice.natural_sample_rate_hertz = 24000
        self.mock_voices_response.voices = [mock_voice]
        self.mock_tts_client.return_value.list_voices.return_value = self.mock_voices_response
        
        # Create a test instance with mocked components
        self.tts_provider = GoogleTTSProvider()
        self.tts_provider.cache = TTSAudioCache(self.temp_dir)
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop patches
        self.tts_client_patcher.stop()
        
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_tts_synthesis(self):
        """Test basic TTS synthesis."""
        text = "Hello, this is a test."
        
        # Call synthesize
        audio_content = self.tts_provider.synthesize(text)
        
        # Verify TTS client was called correctly
        self.mock_tts_client.return_value.synthesize_speech.assert_called_once()
        
        # Verify returned content
        self.assertEqual(audio_content, b'test_audio_content')
    
    def test_voice_selection(self):
        """Test voice selection logic."""
        # Test default voice
        default_voice = get_voice_for_language("en-US")
        self.assertEqual(default_voice["name"], "en-US-Neural2-F")
        
        # Test African language voice
        swahili_voice = get_voice_for_language("sw")
        self.assertEqual(swahili_voice["name"], "sw-KE-Standard-A")
        
        # Test fallback for unsupported language
        yoruba_voice = get_voice_for_language("yo")
        self.assertIsNotNone(yoruba_voice["fallback"])
    
    def test_tts_cache(self):
        """Test TTS audio caching."""
        text = "Hello, this is a cache test."
        voice_id = "en-US-Neural2-F"
        language_code = "en-US"
        
        # First call should use the TTS service
        self.tts_provider.synthesize(text, voice_id, language_code)
        
        # Reset mock to verify it's not called again
        self.mock_tts_client.return_value.synthesize_speech.reset_mock()
        
        # Second call should use cache
        self.tts_provider.synthesize(text, voice_id, language_code)
        
        # Verify TTS was not called again
        self.mock_tts_client.return_value.synthesize_speech.assert_not_called()
    
    def test_save_to_file(self):
        """Test saving audio to file."""
        audio_content = b'test_audio_content'
        file_path = os.path.join(self.temp_dir, "test_audio.mp3")
        
        # Save to file
        saved_path = self.tts_provider.save_to_file(audio_content, file_path)
        
        # Verify file was saved
        self.assertTrue(os.path.exists(saved_path))
        
        # Verify content
        with open(saved_path, 'rb') as f:
            saved_content = f.read()
        self.assertEqual(saved_content, audio_content)
    
    def test_list_voices(self):
        """Test listing available voices."""
        voices = self.tts_provider.get_available_voices()
        
        # Verify client was called
        self.mock_tts_client.return_value.list_voices.assert_called_once()
        
        # Verify returned data
        self.assertEqual(len(voices), 1)
        self.assertEqual(voices[0]["name"], "en-US-Neural2-F")
    
    def test_factory_method(self):
        """Test the TTS factory method."""
        with patch('src.tts.GoogleTTSProvider') as mock_google_provider:
            # Configure the mock to return a specific instance
            provider_instance = MagicMock(spec=TTSProvider)
            mock_google_provider.return_value = provider_instance
            
            # Get provider through factory
            with patch('src.tts.settings') as mock_settings:
                mock_settings.GOOGLE_TTS_ENABLED = True
                provider = get_tts_provider()
            
            # Verify correct provider was created
            mock_google_provider.assert_called_once()
            self.assertEqual(provider, provider_instance)

class TestVoiceProfiles(unittest.TestCase):
    """Test the voice profile selection logic."""
    
    # def test_african_voices_configuration(self):
    #     """Test that all required African languages have voice profiles."""
    #     required_languages = ["en-ZA", "sw", "ar", "yo", "ha", "zu", "af"]
        
    #     self.assertGreaterEqual(len(AFRICAN_VOICE_PROFILES), 1, "At least one voice profile required")
    #     for lang in required_languages:
    #         self.assertIn(lang, AFRICAN_VOICE_PROFILES, f"No voice profile for {lang}")
    
    def test_voice_fallbacks(self):
        """Test that all voice profiles have fallbacks configured."""
        for lang, profile in AFRICAN_VOICE_PROFILES.items():
            self.assertIn("fallback", profile, f"No fallback for {lang}")
            self.assertIsNotNone(profile["fallback"])

if __name__ == "__main__":
    unittest.main()
    