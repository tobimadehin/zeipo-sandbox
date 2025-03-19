import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from src.nlp.intent_matcher import IntentMatcher
from src.nlp.entity_extractor import EntityExtractor, EntityType
from src.nlp.response_templates import ResponseGenerator  
from src.nlp.intent_processor import IntentProcessor
from src.nlp.intent_patterns import IntentType
from static.constants import (
    AMOUNT_TEXTS, COMPOUND_TEXTS, DATE_TEXTS, 
    DURATION_TEXTS, EMAIL_TEXTS, GREETING_TEXTS, 
    HELP_TEXTS, INQUIRY_TEXTS, PAYMENT_TEXTS, 
    PERCENTAGE_TEXTS, PHONE_TEXTS, TIME_TEXTS, 
    UNKNOWN_TEXTS
)

class TestIntentMatcher(unittest.TestCase):
    """Test the Intent Matcher component."""
    
    def setUp(self):
        """Set up the matcher instance."""
        self.matcher = IntentMatcher()
    
    def test_match_intent_greeting(self):
        """Test that greeting intents are correctly matched."""
        greeting_texts = GREETING_TEXTS
        
        for text in greeting_texts:
            intent, confidence = self.matcher.match_intent(text)
            self.assertEqual(intent, IntentType.GREETING)
            self.assertGreaterEqual(confidence, 0.5)
    
    def test_match_intent_payment_or_inquiry(self):
        """Test that payment intents are correctly matched."""
        payment_texts = PAYMENT_TEXTS
        
        for text in payment_texts:
            intent, confidence = self.matcher.match_intent(text)
            conditions = [IntentType.PAYMENT, IntentType.INQUIRY]
            self.assertIn(intent, conditions, f"Failed on: {text}")
            self.assertGreaterEqual(confidence, 0.4)    
    def test_match_intent_help(self):
        """Test that help intents are correctly matched."""
        help_texts = HELP_TEXTS
        
        for text in help_texts:
            intent, confidence = self.matcher.match_intent(text)
            self.assertEqual(intent, IntentType.HELP)
            self.assertGreaterEqual(confidence, 0.5)
    
    def test_match_intent_unknown(self):
        """Test that unknown intents return UNKNOWN with low confidence."""
        unknown_texts = UNKNOWN_TEXTS
        
        for text in unknown_texts:
            intent, confidence = self.matcher.match_intent(text)
            self.assertEqual(intent, IntentType.UNKNOWN)
            self.assertLess(confidence, 0.4)
    
    def test_match_compound_intent(self):
        """Test that compound intents are correctly matched."""
        compound_texts = COMPOUND_TEXTS
        
        for text, expected_intent in compound_texts:
            intent, confidence = self.matcher.match_intent(text)
            self.assertEqual(intent, expected_intent)
            self.assertGreaterEqual(confidence, 0.7)
    
    def test_identify_intents(self):
        """Test that multiple intents are identified with threshold."""
        text = "Hello, I need help with my account payment"
        intents = self.matcher.identify_intents(text, threshold=0.4)
        
        # Should identify at least GREETING, HELP, ACCOUNT, and PAYMENT
        intent_types = [intent[0] for intent in intents]
        
        self.assertIn(IntentType.GREETING, intent_types)
        self.assertIn(IntentType.HELP, intent_types)
        self.assertIn(IntentType.ACCOUNT, intent_types)
        self.assertIn(IntentType.PAYMENT, intent_types)
        
        # First intent should have highest confidence
        self.assertGreaterEqual(intents[0][1], intents[1][1])


class TestEntityExtractor(unittest.TestCase):
    """Test the Entity Extractor component."""
    
    def setUp(self):
        """Set up the extractor instance."""
        self.extractor = EntityExtractor()
    
    def test_extract_date_entities(self):
        """Test extracting date entities."""
        date_texts = DATE_TEXTS
        
        for text in date_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.DATE, entities)
            self.assertGreaterEqual(len(entities[EntityType.DATE]), 1)
    
    def test_extract_time_entities(self):
        """Test extracting time entities."""
        time_texts = TIME_TEXTS
        
        for text in time_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.TIME, entities)
            self.assertGreaterEqual(len(entities[EntityType.TIME]), 1)
    
    def test_extract_phone_number_entities(self):
        """Test extracting phone number entities."""
        phone_texts = PHONE_TEXTS
        
        for text in phone_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.PHONE_NUMBER, entities)
            self.assertGreaterEqual(len(entities[EntityType.PHONE_NUMBER]), 1)
    
    def test_extract_email_entities(self):
        """Test extracting email entities."""
        email_texts = EMAIL_TEXTS
        
        for text in email_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.EMAIL, entities)
            self.assertGreaterEqual(len(entities[EntityType.EMAIL]), 1)
    
    def test_extract_amount_entities(self):
        """Test extracting monetary amount entities."""
        amount_texts = AMOUNT_TEXTS
        
        for text in amount_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.AMOUNT, entities)
            self.assertGreaterEqual(len(entities[EntityType.AMOUNT]), 1)
    
    def test_extract_percentage_entities(self):
        """Test extracting percentage entities."""
        percentage_texts = PERCENTAGE_TEXTS
        
        for text in percentage_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.PERCENTAGE, entities)
            self.assertGreaterEqual(len(entities[EntityType.PERCENTAGE]), 1)
    
    def test_extract_duration_entities(self):
        """Test extracting duration entities."""
        duration_texts = DURATION_TEXTS
        
        for text in duration_texts:
            entities = self.extractor.extract_entities(text)
            self.assertIn(EntityType.DURATION, entities)
            self.assertGreaterEqual(len(entities[EntityType.DURATION]), 1)
    
    def test_extract_multiple_entities(self):
        """Test extracting multiple entity types from a single text."""
        text = "I'd like to schedule a call on January 15, 2023 at 2:30pm. You can reach me at +1-555-123-4567 or user@example.com. My budget is $500."
        
        entities = self.extractor.extract_entities(text)
        
        self.assertIn(EntityType.DATE, entities)
        self.assertIn(EntityType.TIME, entities)
        self.assertIn(EntityType.PHONE_NUMBER, entities)
        self.assertIn(EntityType.EMAIL, entities)
        self.assertIn(EntityType.AMOUNT, entities)
    
    def test_extract_entities_with_positions(self):
        """Test extracting entities with their positions in the text."""
        text = "My appointment is on 01/15/2023 at 2:30pm"
        
        entities = self.extractor.extract_entities_with_positions(text)
        
        self.assertIn(EntityType.DATE, entities)
        self.assertIn(EntityType.TIME, entities)
        
        # Check that positions are correct
        for entity_type, matches in entities.items():
            for match in matches:
                # Each match should be a tuple of (value, start_pos, end_pos)
                self.assertEqual(len(match), 3)
                value, start, end = match
                # The text slice at the positions should equal the value
                self.assertEqual(text[start:end], value)


class TestResponseGenerator(unittest.TestCase):
    """Test the Response Generator component."""
    
    def setUp(self):
        """Set up the generator instance."""
        self.generator = ResponseGenerator()
    
    def test_generate_response_for_intents(self):
        """Test generating responses for different intents."""
        intent_types = [
            IntentType.GREETING,
            IntentType.INQUIRY,
            IntentType.HELP,
            IntentType.ACCOUNT,
            IntentType.PAYMENT,
            IntentType.CONFIRMATION,
            IntentType.REJECTION,
            IntentType.GRATITUDE,
            IntentType.FAREWELL,
            IntentType.UNKNOWN
        ]
        
        for intent in intent_types:
            response = self.generator.generate_response(intent)
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 10)  # Response should be meaningful
    
    def test_generate_response_with_entities(self):
        """Test generating responses enhanced with entity information."""
        # Test account intent with phone number
        entities = {
            EntityType.PHONE_NUMBER: ["+1-555-123-4567"]
        }
        response = self.generator.generate_response(IntentType.ACCOUNT, entities)
        self.assertIn("+1-555-123-4567", response)
        
        # Test payment intent with amount
        entities = {
            EntityType.AMOUNT: ["$50.00"]
        }
        response = self.generator.generate_response(IntentType.PAYMENT, entities)
        self.assertIn("$50.00", response)
        
        # Test inquiry intent with date
        entities = {
            EntityType.DATE: ["January 15, 2023"]
        }
        response = self.generator.generate_response(IntentType.INQUIRY, entities)
        self.assertIn("January 15, 2023", response)
    
    def test_generate_response_with_secondary_intent(self):
        """Test generating responses with secondary intent information."""
        # Test help with account
        response = self.generator.generate_response(
            IntentType.HELP,
            secondary_intent=IntentType.ACCOUNT
        )
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 10)
        self.assertIn("account", response.lower())
        
        # Test inquiry with payment
        response = self.generator.generate_response(
            IntentType.INQUIRY,
            secondary_intent=IntentType.PAYMENT
        )
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 10)
        self.assertIn("payment", response.lower())


class TestIntentProcessor(unittest.TestCase):
    """Test the Intent Processor component."""
    
    def setUp(self):
        """Set up the processor and mocks."""
        self.processor = IntentProcessor()
        self.mock_db = MagicMock(spec=Session)
        self.mock_call_session = MagicMock(id=1, session_id="test_session_1", customer_id=1)
        self.mock_intent = MagicMock(id=1, name="greeting", description="Greeting intent")
            
        def test_process_text(self):
            """Test processing text to detect intents and entities."""
            # Configure mock for THIS test
            def query_side_effect(model_class):
                mock_query = MagicMock()
                
                def filter_side_effect(*args, **kwargs):
                    mock_filter = MagicMock()
                    # Looking for the session - return our mock session
                    if str(args).find("session_id") >= 0 and str(args).find("test_session_1") >= 0:
                        mock_filter.first.return_value = self.mock_call_session
                    # Looking for an intent - handle the side effect
                    elif str(args).find("name") >= 0:
                        mock_filter.first.side_effect = [None, self.mock_intent]
                    else:
                        mock_filter.first.return_value = None
                    return mock_filter
                    
                mock_query.filter.side_effect = filter_side_effect
                return mock_query
            
            # Set up the side effect
            self.mock_db.query.side_effect = query_side_effect
            
        
    def test_process_text(self):
        """Test processing text to detect intents and entities."""
        text = "Hello, I need help with my account payment of $50 on January 15th"
        session_id = self.mock_call_session.session_id
        
        # Process the text
        results, response = self.processor.process_text(text, session_id, self.mock_db)
        
        # Check results structure
        self.assertIn("primary_intent", results)
        self.assertIn("confidence", results)
        self.assertIn("all_intents", results)
        self.assertIn("entities", results)
        self.assertIn("call_session_id", results)
        self.assertIn("text", results)
        
        # Check response is not empty
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 10)
        
        # Verify DB operations
        self.mock_db.query.assert_called()
        self.mock_db.add.assert_called()
        self.mock_db.commit.assert_called_once()
    
    def test_process_text_session_not_found(self):
        """Test processing text with a non-existent session."""
        # Configure mock to return no session
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        text = "Hello, how are you?"
        session_id = "nonexistent_session"
        
        # Process the text
        results, response = self.processor.process_text(text, session_id, self.mock_db)
        
        # Check error is returned
        self.assertIn("error", results)
        self.assertIn("not found", results["error"])
        
        # Check response indicates error
        self.assertIn("trouble", response.lower())
    
    @patch('src.nlp.intent_matcher.IntentMatcher.match_intent')
    @patch('src.nlp.entity_extractor.EntityExtractor.extract_entities')
    def test_process_text_with_error(self, mock_extract, mock_match):
        """Test error handling during text processing."""
        # Configure mocks to raise an exception
        mock_match.side_effect = Exception("Test error")
        
        text = "Hello, how are you?"
        session_id = "test_session_1"
        
        # Process the text
        results, response = self.processor.process_text(text, session_id, self.mock_db)
        
        # Check error is returned
        self.assertIn("error", results)

if __name__ == "__main__":
    unittest.main()
    