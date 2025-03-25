# src/nlp/intent_processor.py
from typing import Dict, Tuple, Any
from sqlalchemy.orm import Session

from .intent_matcher import IntentMatcher
from .entity_extractor import EntityExtractor
from .response_templates import ResponseGenerator

from db.models import CallSession, CallIntent, Intent, Entity
from static.constants import logger
from db.session import SessionLocal

class IntentProcessor:
    """
    Class for processing transcribed text to detect intents and entities,
    storing them in the database, and generating appropriate responses.
    """
    
    def __init__(self):
        """Initialize the intent processor with required components."""
        self.matcher = IntentMatcher()
        self.extractor = EntityExtractor()
        self.generator = ResponseGenerator()
    
    def process_text(
        self, 
        text: str, 
        session_id: str, 
        db: Session = None
    ) -> Tuple[Dict[str, Any], str]:
        """
        Process transcribed text to detect intents and entities.
        
        Args:
            text: The transcribed text to process
            session_id: The call session ID
            db: Database session (optional)
            
        Returns:
            Tuple of (processing_results, response_text)
        """
        # Create a database session if not provided
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Get call session
            call_session = db.query(CallSession).filter(CallSession.session_id == session_id).first()
            if not call_session:
                logger.error(f"Call session not found: {session_id}")
                return {"error": "Call session not found"}, "I'm sorry, but I'm having trouble with your call session."
            
            # Detect intents
            primary_intent, confidence = self.matcher.match_intent(text)
            all_intents = self.matcher.identify_intents(text)
            
            # Get or create intents in database
            intent_records = []
            for intent_type, score in all_intents:
                # Find or create intent
                intent_name = intent_type.name.lower()
                intent = db.query(Intent).filter(Intent.name == intent_name).first()
                if not intent:
                    intent = Intent(name=intent_name, description=f"{intent_type.name} intent")
                    db.add(intent)
                    db.flush()
                
                # Create call intent record
                call_intent = CallIntent(
                    call_session_id=call_session.id,
                    intent_id=intent.id,
                    confidence=score
                )
                db.add(call_intent)
                intent_records.append(call_intent)
            
            # Extract entities
            entities_dict = self.extractor.extract_entities(text)
            
            # Store entities in database
            entity_records = []
            for entity_type, values in entities_dict.items():
                for value in values:
                    entity = Entity(
                        call_session_id=call_session.id,
                        entity_type=entity_type.name.lower(),
                        entity_value=value
                    )
                    db.add(entity)
                    entity_records.append(entity)
            
            # Commit changes to database
            db.commit()
            
            # Determine secondary intent for compound response
            secondary_intent = None
            if len(all_intents) > 1:
                secondary_intent = all_intents[1][0]
            
            # Generate response
            response = self.generator.generate_response(
                primary_intent,
                entities_dict,
                secondary_intent
            )
            
            # Prepare results
            results = {
                "primary_intent": primary_intent.name,
                "confidence": confidence,
                "all_intents": [(intent.name, score) for intent, score in all_intents],
                "entities": {entity_type.name: values for entity_type, values in entities_dict.items()},
                "session_id": session_id,
                "text": text
            }
            
            return results, response
            
        except Exception as e:
            logger.error(f"Error processing intent: {str(e)}")
            if db.is_active:
                db.rollback()
            return {"error": str(e)}, "I'm sorry, but I experienced an error while processing your request."
            
        finally:
            if close_db:
                db.close()
                