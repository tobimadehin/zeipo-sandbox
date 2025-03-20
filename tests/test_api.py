import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime
import tempfile

from main import app

client = TestClient(app)

class TestAPIEndpoints(unittest.TestCase):
    """Test the main API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock session for database operations
        self.db_session_patcher = patch('db.session.SessionLocal')
        self.mock_db_session = self.db_session_patcher.start()
        
        # Create mock db instance
        self.mock_db = MagicMock()
        self.mock_db_session.return_value = self.mock_db
        
        # Setup mock query results
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Setup mock commit
        self.mock_db.commit = MagicMock()
        
    def tearDown(self):
        """Clean up after tests."""
        self.db_session_patcher.stop()
    
    def test_root_endpoint(self):
        """Test the root endpoint returns basic information."""
        response = client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check essential fields
        self.assertIn("name", data)
        self.assertIn("status", data)
        self.assertIn("models", data)
        self.assertIn("device", data)
        self.assertIn("cuda_available", data)
        
        # Check models list
        self.assertIsInstance(data["models"], list)
        self.assertIn("tiny", data["models"])
        self.assertIn("small", data["models"])
    
    def test_calls_list_endpoint(self):
        """Test the calls listing endpoint."""
        # Mock the calls list
        mock_calls = [
            MagicMock(
                id=1,
                session_id="test_session_1",
                customer_id=1,
                start_time=datetime.now()
            ),
            MagicMock(
                id=2,
                session_id="test_session_2",
                customer_id=2,
                start_time=datetime.now()
            )
        ]
        self.mock_db.query.return_value.all.return_value = mock_calls
        
        response = client.get("/api/v1/calls")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], 1)
        self.assertEqual(data[0]["session_id"], "test_session_1")
        self.assertEqual(data[1]["id"], 2)
        self.assertEqual(data[1]["session_id"], "test_session_2")
    
    def test_call_detail_endpoint(self):
        """Test retrieving a specific call by session ID."""
        # Mock the call
        mock_call = MagicMock(
            id=1,
            session_id="test_session_1",
            customer_id=1,
            start_time=datetime.now()
        )
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_call
        
        response = client.get("/api/v1/calls/test_session_1")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["session_id"], "test_session_1")
        self.assertEqual(data["customer_id"], 1)
    
    def test_call_detail_endpoint_not_found(self):
        """Test retrieving a non-existent call returns 404."""
        # Mock no call found
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.get("/api/v1/calls/nonexistent_session")
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"])
    
    def test_end_call_endpoint(self):
        """Test ending a call session."""
        # Mock the call
        mock_call = MagicMock(
            id=1,
            session_id="test_session_1",
            customer_id=1,
            start_time=datetime.now() 
        )
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_call
        
        response = client.patch("/api/v1/calls/test_session_1?recording_url=https://example.com/recording.mp3&escalated=true")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["call_id"], 1)
        
        # Verify the call was updated correctly
        self.assertIsNotNone(mock_call.end_time)
        self.assertIsNotNone(mock_call.duration_seconds)
        self.assertEqual(mock_call.recording_url, "https://example.com/recording.mp3")
        self.assertTrue(mock_call.escalated)
        
        # Verify commit was called
        self.mock_db.commit.assert_called_once()
    
    @patch('src.api.audio.process_audio')
    def test_transcribe_audio_endpoint(self, mock_process_audio):
        """Test the audio transcription endpoint."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'test audio content')
            temp_file.flush()
            
            # Mock the process_audio result
            mock_process_audio.return_value = {
                "text": "Test transcription",
                "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "Test transcription"}],
                "_performance": {
                    "process_time": 0.5,
                    "audio_duration": 1.0,
                    "real_time_factor": 0.5,
                    "device": "cpu"
                }
            }
            
            # Test file upload
            with open(temp_file.name, 'rb') as f:
                response = client.post(
                    "/api/v1/audios/transcribe",
                    files={"file": ("test.mp3", f, "audio/mpeg")},
                    data={"model": "tiny", "task": "transcribe"}
                )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Check response structure
            self.assertEqual(data["text"], "Test transcription")
            self.assertIn("segments", data)
            self.assertIn("_performance", data)
    
    def test_transcribe_audio_invalid_model(self):
        """Test transcription with invalid model returns error."""
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'test audio content')
            temp_file.flush()
            
            # Test file upload with invalid model
            with open(temp_file.name, 'rb') as f:
                response = client.post(
                    "/api/v1/audios/transcribe",
                    files={"file": ("test.mp3", f, "audio/mpeg")},
                    data={"model": "nonexistent", "task": "transcribe"}
                )
            
            self.assertEqual(response.status_code, 400)
            data = response.json()
            self.assertIn("detail", data)
            self.assertIn("not available", data["detail"])
    
    def test_nlu_process_endpoint(self):
        """Test the NLU processing endpoint."""
        # Setup mocks for NLU processing
        mock_call_session = MagicMock(id=1, session_id="test_session_1")
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_call_session
        
        with patch('src.nlp.intent_processor.IntentProcessor.process_text') as mock_process:
            # Mock the process_text result
            mock_process.return_value = (
                {
                    "primary_intent": "GREETING",
                    "confidence": 0.9,
                    "all_intents": [("GREETING", 0.9), ("INQUIRY", 0.2)],
                    "entities": {},
                    "call_session_id": "test_session_1",
                    "text": "Hello, how are you?"
                },
                "Hello! How can I assist you today?"
            )
            
            # Make request
            response = client.post(
                "/api/v1/nlu",
                json={
                    "text": "Hello, how are you?",
                    "session_id": "test_session_1"
                }
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Check response structure
            self.assertEqual(data["primary_intent"], "GREETING")
            self.assertEqual(data["confidence"], 0.9)
            self.assertIn("all_intents", data)
            self.assertIn("entities", data)
            self.assertEqual(data["response"], "Hello! How can I assist you today?")
            self.assertEqual(data["session_id"], "test_session_1")
            self.assertEqual(data["text"], "Hello, how are you?")
    
    def test_nlu_process_session_not_found(self):
        """Test NLU processing with non-existent session returns 404."""
        # Mock no session found
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            "/api/v1/nlu",
            json={
                "text": "Hello, how are you?",
                "session_id": "nonexistent_session"
            }
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"])
    
    def test_transcription_segment_endpoint(self):
        """Test adding a transcription segment."""
        # Mock the call session
        mock_call_session = MagicMock(id=1, session_id="test_session_1")
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_call_session
        
        # Mock the transcription
        mock_transcription = MagicMock(id=1)
        self.mock_db.add = MagicMock()
        
        # Send request to the correct endpoint
        response = client.post(
            "/api/v1/transcriptions", 
            json={
                "session_id": "test_session_1",
                "transcript": "Hello, world!",
                "speaker": "caller",
                "segment_start_time": 0.0,
                "segment_end_time": 2.5
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response
        self.assertEqual(data["status"], "success")
        
        # Verify db operations
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
    
    def test_system_gpu_info_endpoint(self):
        """Test the GPU info endpoint."""
        # This is a simple test that just ensures the endpoint responds
        response = client.get("/api/v1/system/gpu")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check essential fields
        self.assertIn("cuda_available", data) 

if __name__ == "__main__":
    unittest.main()
    