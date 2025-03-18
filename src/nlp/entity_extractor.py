# src/nlp/entity_extractor.py
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import calendar
from enum import Enum, auto

class EntityType(Enum):
    """Enumeration of recognized entity types."""
    DATE = auto()
    TIME = auto()
    PHONE_NUMBER = auto()
    EMAIL = auto()
    NUMBER = auto()
    AMOUNT = auto()
    PERCENTAGE = auto()
    DURATION = auto()
    PERSON_NAME = auto()
    LOCATION = auto()

# Entity extraction patterns
ENTITY_PATTERNS = {
    EntityType.DATE: [
        # MM/DD/YYYY or DD/MM/YYYY
        re.compile(r'\b(0?[1-9]|[12][0-9]|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2}|\d{2})\b'),
        re.compile(r'\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])[-/](20\d{2}|\d{2})\b'),
        
        # Month name patterns
        re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?,?\s+(20\d{2}|\d{2})\b', re.IGNORECASE),
        re.compile(r'\b(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(20\d{2}|\d{2})\b', re.IGNORECASE),
        
        # Relative dates
        re.compile(r'\b(today|tomorrow|yesterday)\b', re.IGNORECASE),
        re.compile(r'\b(this|next|last)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|week|month|year)\b', re.IGNORECASE),
    ],
    
    EntityType.TIME: [
        # HH:MM format (12-hour and 24-hour)
        re.compile(r'\b(0?[1-9]|1[0-2])[:\.](0?[0-9]|[1-5][0-9])\s*(am|pm)?\b', re.IGNORECASE),
        re.compile(r'\b([01]?[0-9]|2[0-3])[:\.](0?[0-9]|[1-5][0-9])\b'),
        
        # Common time expressions
        re.compile(r'\b(noon|midnight|morning|afternoon|evening|night)\b', re.IGNORECASE),
    ],
    
    EntityType.PHONE_NUMBER: [
        # International format: +1 555-123-4567, +44 (20) 1234 5678, +81-3-1234-5678
        re.compile(r'\+\d{1,3}\s?[- ]?\(?\d{1,4}\)?[- ]?\d{1,4}[- ]?\d{1,9}'),
        
        # US format: (555) 123-4567, 555-123-4567, 5551234567
        re.compile(r'\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}'),
        
        # Nigerian format: 08012345678, 09087654321, 07023456789
        re.compile(r'0\d{10}'),
    ],
    
    EntityType.EMAIL: [
        re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'),
    ],
    
    EntityType.NUMBER: [
        re.compile(r'\b\d+\b'),
    ],
    
    EntityType.AMOUNT: [
        # Currency amounts with symbols
        re.compile(r'\$\s*\d+(?:\.\d{1,2})?'),
        re.compile(r'\£\s*\d+(?:\.\d{1,2})?'),
        re.compile(r'\€\s*\d+(?:\.\d{1,2})?'),
        re.compile(r'\₦\s*\d+(?:\.\d{1,2})?'),
        
        # Currency amounts with names
        re.compile(r'\b\d+(?:\.\d{1,2})?\s+(?:dollars|euros|pounds|naira)\b', re.IGNORECASE),
        re.compile(r'\b(?:USD|EUR|GBP|NGN)\s*\d+(?:\.\d{1,2})?\b'),
    ],
    
    EntityType.PERCENTAGE: [
        re.compile(r'\b\d+(?:\.\d+)?\s*%\b'),
        re.compile(r'\b\d+(?:\.\d+)?\s+percent\b', re.IGNORECASE),
    ],
    
    EntityType.DURATION: [
        re.compile(r'\b(\d+)\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b', re.IGNORECASE),
    ],
}

class EntityExtractor:
    """Class for extracting entities from text using regex patterns."""
    
    def __init__(self):
        """Initialize the entity extractor with precompiled patterns."""
        self.patterns = ENTITY_PATTERNS
    
    def extract_entities(self, text: str) -> Dict[EntityType, List[str]]:
        """
        Extract entities from the given text.
        
        Args:
            text: The text to analyze for entities
            
        Returns:
            Dictionary mapping entity types to lists of extracted values
        """
        if not text or not isinstance(text, str):
            return {}
        
        results: Dict[EntityType, List[str]] = {}
        
        # Check each entity type
        for entity_type, patterns in self.patterns.items():
            matches = []
            for pattern in patterns:
                pattern_matches = pattern.findall(text)
                if pattern_matches:
                    # Flatten tuple matches or use string matches directly
                    for match in pattern_matches:
                        if isinstance(match, tuple):
                            # For tuple matches (like date components), join with a space
                            matches.append(' '.join(match).strip())
                        else:
                            matches.append(match)
            
            if matches:
                results[entity_type] = matches
        
        return results
    
    def extract_entities_with_positions(self, text: str) -> Dict[EntityType, List[Tuple[str, int, int]]]:
        """
        Extract entities from the given text with their positions.
        
        Args:
            text: The text to analyze for entities
            
        Returns:
            Dictionary mapping entity types to lists of tuples (value, start_pos, end_pos)
        """
        if not text or not isinstance(text, str):
            return {}
        
        results: Dict[EntityType, List[Tuple[str, int, int]]] = {}
        
        # Check each entity type
        for entity_type, patterns in self.patterns.items():
            matches = []
            for pattern in patterns:
                for match in pattern.finditer(text):
                    start_pos = match.start()
                    end_pos = match.end()
                    value = match.group(0)
                    matches.append((value, start_pos, end_pos))
            
            if matches:
                # Sort by position
                matches.sort(key=lambda x: x[1])
                results[entity_type] = matches
        
        return results
    