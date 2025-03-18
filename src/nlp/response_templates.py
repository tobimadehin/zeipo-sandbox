# src/nlp/response_templates.py
from typing import Dict, List
import random

from static.constants import COMPOUND_RESPONSE_TEMPLATES, RESPONSE_TEMPLATES
from .intent_patterns import IntentType
from .entity_extractor import EntityType


class ResponseGenerator:
    """Class for generating responses based on intent and entities."""
    
    def __init__(self):
        """Initialize the response generator with templates."""
        self.templates = RESPONSE_TEMPLATES
        self.compound_templates = COMPOUND_RESPONSE_TEMPLATES
    
    def generate_response(
        self, 
        intent: IntentType, 
        entities: Dict[EntityType, List[str]] = None,
        secondary_intent: IntentType = None
    ) -> str:
        """
        Generate a response based on detected intent and entities.
        
        Args:
            intent: The primary detected intent
            entities: Dictionary of extracted entities (optional)
            secondary_intent: Secondary intent for compound responses (optional)
            
        Returns:
            Generated response text
        """
        entities = entities or {}
        
        # Check for compound intent match first
        if secondary_intent and (intent, secondary_intent) in self.compound_templates:
            templates = self.compound_templates[(intent, secondary_intent)]
            base_response = random.choice(templates)
        else:
            # Fall back to single intent template
            templates = self.templates.get(intent, self.templates[IntentType.UNKNOWN])
            base_response = random.choice(templates)
        
        # Enhance response with entity information if available
        enhanced_response = self._enhance_with_entities(base_response, intent, entities)
        
        return enhanced_response
    
    def _enhance_with_entities(
        self, 
        base_response: str, 
        intent: IntentType, 
        entities: Dict[EntityType, List[str]]
    ) -> str:
        """
        Enhance the base response with entity information.
        
        Args:
            base_response: The base response template
            intent: The detected intent
            entities: Dictionary of extracted entities
            
        Returns:
            Enhanced response with entity information
        """
        enhanced_response = base_response
        
        # Add entity-specific enhancements based on intent
        if intent == IntentType.ACCOUNT and EntityType.PHONE_NUMBER in entities:
            enhanced_response += f" I see you're calling from {entities[EntityType.PHONE_NUMBER][0]}."
        
        elif intent == IntentType.PAYMENT and EntityType.AMOUNT in entities:
            enhanced_response += f" I notice you mentioned the amount {entities[EntityType.AMOUNT][0]}."
        
        elif intent == IntentType.INQUIRY and EntityType.DATE in entities:
            enhanced_response += f" Regarding the date you mentioned, {entities[EntityType.DATE][0]}."
        
        return enhanced_response
    