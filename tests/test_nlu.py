import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from main import app
from db.models import CallSession, Customer
from src.nlp.intent_patterns import IntentType
from src.nlp.entity_extractor import EntityType
from src.nlu.intent_understanding import intent_processor

client = TestClient(app)

class TestNLUEndpoint(unittest.TestCase):
    """Test the NLU API endpoint."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock session for database operations
        self.db_session_patcher = patch('db.session.SessionLocal')
        self.mock_db_session = self.db_session_patcher.start()
        
        # Create mock db instance
        self.mock_db = MagicMock()
        self.mock_db_session.return_value = self.mock_db
        
        # Setup mock call session
        self.mock_call_session = MagicMock(
            id=1,
            session_id="test_session_1",
            customer_id=1
        )
        
        # Set up mock query results
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_call_session
        
        # Setup mock commit
        self.mock_db.commit = MagicMock()
        
        # Patch intent processor
        self.intent_processor_patcher = patch('src.nlp.intent_processor.IntentProcessor.process_text')
        self.mock_process_text = self.intent_processor_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.db_session_patcher.stop()
        self.intent_processor_patcher.stop()
    
    def test_nlu_process_greeting(self):
        """Test NLU processing of a greeting."""
        # Set up mock process_text return value
        self.mock_process_text.return_value = (
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
            "/api/v1/nlu/",
            json={
                "text": "Hello, how are you?",
                "session_id": "test_session_1"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["primary_intent"], "GREETING")
        self.assertEqual(data["confidence"], 0.9)
        self.assertEqual(len(data["all_intents"]), 2)
        self.assertEqual(data["all_intents"][0]["intent"], "GREETING")
        self.assertEqual(data["all_intents"][0]["confidence"], 0.9)
        self.assertEqual(data["response"], "Hello! How can I assist you today?")
    
    def test_nlu_process_help_with_account(self):
        """Test NLU processing of a help request with account."""
        # Set up mock process_text return value with entities
        self.mock_process_text.return_value = (
            {
                "primary_intent": "HELP",
                "confidence": 0.85,
                "all_intents": [("HELP", 0.85), ("ACCOUNT", 0.75)],
                "entities": {"ACCOUNT": ["account"]},
                "call_session_id": "test_session_1",
                "text": "I need help with my account"
            },
            "I'd be happy to help with your account. What specific issue are you having with your account?"
        )
        
        # Make request
        response = client.post(
            "/api/v1/nlu/",
            json={
                "text": "I need help with my account",
                "session_id": "test_session_1"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["primary_intent"], "HELP")
        self.assertEqual(data["confidence"], 0.85)
        self.assertIn("account", data["response"].lower())
    
    def test_nlu_process_payment_with_amount(self):
        """Test NLU processing of a payment inquiry with amount."""
        # Set up mock process_text return value with entities
        self.mock_process_text.return_value = (
            {
                "primary_intent": "PAYMENT",
                "confidence": 0.8,
                "all_intents": [("PAYMENT", 0.8), ("INQUIRY", 0.6)],
                "entities": {"AMOUNT": ["$50.00"]},
                "call_session_id": "test_session_1",
                "text": "I want to make a payment of $50.00"
            },
            "I can assist with payment-related questions. I notice you mentioned the amount $50.00."
        )
        
        # Make request
        response = client.post(
            "/api/v1/nlu/",
            json={
                "text": "I want to make a payment of $50.00",
                "session_id": "test_session_1"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["primary_intent"], "PAYMENT")
        self.assertEqual(data["confidence"], 0.8)
        self.assertIn("$50.00", data["response"])
    
    def test_nlu_process_multiple_entities(self):
        """Test NLU processing with multiple entity types."""
        # Set up mock process_text return value with multiple entities
        self.mock_process_text.return_value = (
            {
                "primary_intent": "INQUIRY",
                "confidence": 0.75,
                "all_intents": [("INQUIRY", 0.75), ("PAYMENT", 0.6)],
                "entities": {
                    "DATE": ["January 15, 2023"],
                    "AMOUNT": ["$75.50"],
                    "PHONE_NUMBER": ["+1-555-123-4567"]
                },
                "call_session_id": "test_session_1",
                "text": "When will my $75.50 payment be processed on January 15, 2023? Call me at +1-555-123-4567"
            },
            "I'll do my best to answer your question. Regarding the date you mentioned, January 15, 2023."
        )
        
        # Make request
        response = client.post(
            "/api/v1/nlu/",
            json={
                "text": "When will my $75.50 payment be processed on January 15, 2023? Call me at +1-555-123-4567",
                "session_id": "test_session_1"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["primary_intent"], "INQUIRY")
        self.assertEqual(data["confidence"], 0.75)
        self.assertIn("DATE", data["entities"])
        self.assertIn("AMOUNT", data["entities"])
        self.assertIn("PHONE_NUMBER", data["entities"])
    
    def test_nlu_process_session_not_found(self):
        """Test NLU processing with non-existent session."""
        # Configure mock to return no session
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Make request
        response = client.post(
            "/api/v1/nlu/",
            json={
                "text": "Hello, how are you?",
                "session_id": "nonexistent_session"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"])
    
    def test_nlu_process_error_handling(self):
        """Test error handling during NLU processing."""
        # Configure mock to indicate an error
        self.mock_process_text.return_value = (
            {"error": "Test error occurred"},
            "I'm sorry, but I experienced an error while processing your request."
        )
        
        # Make request
        response = client.post(
            "/api/v1/nlu/",
            json={
                "text": "This will cause an error",
                "session_id": "test_session_1"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("detail", data)
        self.assertEqual(data["detail"], "Test error occurred")
    
    def test_real_intent_processor(self):
        """Test with the real IntentProcessor for end-to-end verification."""
        # Temporarily restore the real processor
        self.intent_processor_patcher.stop()
        
        try:
            # Test with some basic intents that should work without DB dependencies
            with patch('db.session.SessionLocal') as mock_session:
                # Configure mock session
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                
                # Mock the call session
                mock_call = MagicMock(
                    id=1,
                    session_id="test_session_1",
                    customer_id=1
                )
                mock_db.query.return_value.filter.return_value.first.return_value = mock_call
                
                # Mock database operations
                mock_db.add = MagicMock()
                mock_db.commit = MagicMock()
                
                # Test with a simple greeting
                response = client.post(
                    "/api/v1/nlu/",
                    json={
                        "text": "Hello",
                        "session_id": "test_session_1"
                    }
                )
                
                # Should succeed
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["primary_intent"], "GREETING")
        
        finally:
            # Restore the mock
            self.mock_process_text = self.intent_processor_patcher.start()


if __name__ == "__main__":
    unittest.main()
    