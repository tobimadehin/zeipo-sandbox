# src/nlp/intent_matcher.py
from typing import Dict, List, Tuple
from .intent_patterns import IntentType, INTENT_PATTERNS, COMPOUND_PATTERNS

class IntentMatcher:
    """Class for matching intents in text using regex patterns."""
    
    def __init__(self):
        """Initialize the intent matcher with precompiled patterns."""
        self.patterns = INTENT_PATTERNS
        self.compound_patterns = COMPOUND_PATTERNS
    
    def match_intent(self, text: str) -> Tuple[IntentType, float]:
        """
        Match the intent in the given text.
        
        Args:
            text: The text to analyze for intent
            
        Returns:
            Tuple of (intent_type, confidence_score)
        """
        if not text or not isinstance(text, str):
            return IntentType.UNKNOWN, 0.0
        
        # Check for compound intents first
        for intent_pair, pattern in self.compound_patterns.items():
            if pattern.search(text):
                # Return the first intent of the pair with high confidence
                return intent_pair[0], 0.9
        
        # Check each intent type
        intent_scores: Dict[IntentType, float] = {}
        for intent_type, patterns in self.patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    # Score based on match count and text coverage
                    match_score = min(len(matches) * 0.3, 0.7)  # Cap at 0.6 for multiple matches
                    coverage = sum(len(match) for match in matches) / max(len(text), 1)
                    score = max(score, match_score + (coverage * 0.2))  # Max 0.9
                    
            if score > 0:
                intent_scores[intent_type] = score
        
        # Get the intent with highest score
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            return best_intent[0], best_intent[1]
        
        # No intent matched
        return IntentType.UNKNOWN, 0.0
    
    def identify_intents(self, text: str, threshold: float = 0.4) -> List[Tuple[IntentType, float]]:
        """
        Identify all possible intents in the text above the threshold.
        
        Args:
            text: The text to analyze
            threshold: Minimum confidence score to include an intent
            
        Returns:
            List of (intent_type, confidence_score) tuples, sorted by confidence
        """
        if not text or not isinstance(text, str):
            return []
        
        intent_scores: Dict[IntentType, float] = {}
        
        # Check each intent type
        for intent_type, patterns in self.patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    match_score = min(len(matches) * 0.2, 0.6)
                    coverage = sum(len(match) for match in matches) / max(len(text), 1)
                    score = max(score, match_score + (coverage * 0.3))
                    
            if score >= threshold:
                intent_scores[intent_type] = score
        
        # Sort by confidence score descending
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_intents
    