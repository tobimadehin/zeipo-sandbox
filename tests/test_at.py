# app/tests/test_at.py
import unittest
from fastapi.testclient import TestClient
import os
import json
from main import app
from xml.etree import ElementTree as ET

from src.api.integrations.at import build_voice_response
from src.utils.helpers import gen_uuid_12

client = TestClient(app)

class TestAfricasTalkingIntegration(unittest.TestCase):
    """Test the Africa's Talking integration."""
    
    def test_voice_webhook(self):
        """Test the voice webhook endpoint."""
        # Simulate an Africa's Talking voice webhook call
        response = client.post(
            "/api/v1/integrations/at/voice",
            data={
                "sessionId": "AT_TEST_123456789",
                "callerNumber": "+2347012345678",
                "direction": "inbound",
                "isActive": "1",
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/xml")
        
        # Try to parse the XML response
        try:
            ET.fromstring(response.content)
            valid_xml = True
        except:
            valid_xml = False
        
        self.assertTrue(valid_xml, "Response should be valid XML")
        
        # Check that the XML contains Voice XML elements
        self.assertIn("<Response>", response.text)
        self.assertIn("<Say>", response.text)
    
    def test_events_webhook(self):
        """Test the events webhook endpoint."""
        # Create a test call first
        client.post(
            "/api/v1/integrations/at/voice",
            data={
                "sessionId": "AT_EVENT_TEST_123",
                "callerNumber": "+2347087654321",
                "direction": "inbound",
                "isActive": "1",
            }
        )
        
        # Now simulate an events callback
        response = client.post(
            "/api/v1/integrations/at/events",
            data={
                "sessionId": "AT_EVENT_TEST_123",
                "status": "completed",
                "durationInSeconds": "120",
                "direction": "inbound"
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
    
    def test_dtmf_webhook(self):
        """Test the DTMF webhook endpoint."""
        response = client.post(
            "/api/v1/integrations/at/dtmf",
            data={
                "sessionId": "AT_DTMF_TEST_123",
                "dtmfDigits": "12345",
            }
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/xml")
        
        # Check XML content
        self.assertIn("<Response>", response.text)
        self.assertIn("<Say>", response.text)
        self.assertIn("You entered", response.text)
    
    def test_call_logging(self):
        """Test that calls are logged to files."""
        # Generate a unique call SID for this test
        test_session_id = f"AT_LOG_TEST_{gen_uuid_12()}"
        phone = "+2347055551234"
        
        # Simulate a call
        client.post(
            "/api/integrations/v1/at/voice",
            data={
                "sessionId": test_session_id,
                "callerNumber": phone,
                "direction": "inbound",
                "isActive": "1",
            }
        )
        
        # Check if log file was created
        log_path = f"logs/calls/{test_session_id}.json"
        self.assertTrue(os.path.exists(log_path), f"Log file {log_path} should exist")
        
        # Check log content
        with open(log_path, 'r') as f:
            log_data = json.load(f)
        
        # Verify log data
        self.assertEqual(log_data["call_sid"], test_session_id)
        self.assertEqual(log_data["phone_number"], phone)
    
    def test_voice_xml_generation(self):
        """Test XML generation functions."""
        
        # Test simple say response
        xml = build_voice_response(say_text="Hello, test")
        self.assertIn("<Response>", xml)
        self.assertIn("<Say>Hello, test</Say>", xml)
        
        # Test GetDigits response
        xml = build_voice_response(get_digits={
            "say": "Please enter your PIN",
            "config": {
                "timeout": 20,
                "finishOnKey": "#",
                "numDigits": 4
            }
        })
        self.assertIn("<GetDigits", xml)
        self.assertIn("timeout=\"20\"", xml)
        self.assertIn("numDigits=\"4\"", xml)
        self.assertIn("<Say>Please enter your PIN</Say>", xml)

if __name__ == "__main__":
    unittest.main()
    