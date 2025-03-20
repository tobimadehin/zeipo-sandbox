# src/nlp/intent_patterns.py
import re
from typing import Dict, List, Pattern
from enum import Enum, auto

class IntentType(Enum):
    """
    Represents categories of user intents the system can recognize.
    Each member includes example phrases it should detect.
    
    Design Note: Order matters - compound patterns using these intents 
    should be defined after their component intents exist.
    """
    GREETING = auto()       # "Hello!", "Good morning team!"
    INQUIRY = auto()        # "How do I reset my password?"
    HELP = auto()           # "I need technical support"
    ACCOUNT = auto()        # "Can't access my profile"
    PAYMENT = auto()        # "Why was I charged ₦3000 twice?"
    COMPLAINT = auto()      # "Your app crashed again!"
    CONFIRMATION = auto()   # "Yes, confirm order"
    REJECTION = auto()      # "No, cancel that request"
    GRATITUDE = auto()      # "Thanks for the help!"
    FAREWELL = auto()       # "Goodbye for now"
    UNKNOWN = auto()        # Fallback for unrecognized inputs

# Primary intent detection patterns
# Format: {Intent: [list_of_regex_patterns]}
# Matching Priority: Patterns are checked in sequence, first match wins
INTENT_PATTERNS: Dict[IntentType, List[Pattern]] = {
    IntentType.GREETING: [
        # Matches opening salutations
        re.compile(r'\b(?:hello|hi|hey|greetings|good\s+(?:morning|afternoon|evening|day))\b', re.IGNORECASE),
    ],
    IntentType.INQUIRY: [
        # Question patterns (how/what/where/when/why)
        re.compile(r'\b(?:how\s+(?:do|can|could)\s+I|what\s+(?:is|are)|where\s+(?:is|are)|when\s+(?:is|are)|who\s+(?:is|are)|why\s+(?:is|are))\b', re.IGNORECASE),
        # Explicit information requests
        re.compile(r'\b(?:tell\s+me\s+about|explain|describe|inquiry|enquiry|information\s+on)\b', re.IGNORECASE),
        re.compile(r'\b(?:what|where|when|who|why)\s+(?:is|are|does|do)\s+(?!payment)'),
    ],
    IntentType.HELP: [
        # Direct help requests
        re.compile(r'\b(?:help|assist|support|guide|trouble|problem|issue|error)\b', re.IGNORECASE),
        # Personal assistance needs
        re.compile(r'\bi\s+need\s+help\b', re.IGNORECASE),
        # Requests for bot assistance
        re.compile(r'\bcan\s+you\s+help\b', re.IGNORECASE),
    ],
    IntentType.ACCOUNT: [
        # Account-related terminology
        re.compile(r'\b(?:account|login|password|username|profile|sign\s+in|log\s+in)\b', re.IGNORECASE),
    ],
    IntentType.PAYMENT: [
        # Payment processing vocabulary
        re.compile(r'\b(?:pay|payment|bill|invoice|transaction|receipt|credit|debit|charge|subscription|plan)\b', re.IGNORECASE),
    ],
    IntentType.COMPLAINT: [
        # Emotional dissatisfaction terms
        re.compile(r'\b(?:complain|complaint|dissatisfied|unhappy|angry|frustrated|pissed|annoyed|offended)\b', re.IGNORECASE),
        # Service issue descriptors
        re.compile(r'\b(?:issue|problem|slow|delay|charged|wrong|mistake|error|bad\s+service)\b', re.IGNORECASE),
    ],
    IntentType.CONFIRMATION: [
        # Positive affirmations
        re.compile(r'\b(?:yes|yeah|yep|correct|right|sure|absolutely|positive|definitely|of\s+course|proceed)\b', re.IGNORECASE),
    ],
    IntentType.REJECTION: [
        # Negative responses
        re.compile(r'\b(?:no|nope|nah|negative|never|not\s+(?:now|really|at\s+all)|decline|reject)\b', re.IGNORECASE),
    ],
    IntentType.GRATITUDE: [
        # Expressions of thanks
        re.compile(r'\b(?:thank|thanks|appreciate|grateful|gratitude)\b', re.IGNORECASE),
    ],
    IntentType.FAREWELL: [
        # Closing conversations
        re.compile(r'\b(?:bye|goodbye|farewell|see\s+you|talk\s+to\s+you\s+later|have\s+a\s+(?:good|nice))\b', re.IGNORECASE),
    ],
}

# Compound intent patterns (checked before basic patterns)
# Format: {(PrimaryIntent, SecondaryIntent): combined_regex}
# Design Rationale: Handle multi-concept queries with priority over single intents
COMPOUND_PATTERNS = {
    # Help with account issues
    # Matches: "Help! I'm locked out of my account"
    #          "Can you assist with password recovery?"
    (IntentType.HELP, IntentType.ACCOUNT): re.compile(
        r'\b(?:help|assist).{1,30}(?:account|login|password)\b', 
        re.IGNORECASE
    ),
    
    # Payment-related assistance
    # Matches: "I need help with a payment error"
    #          "Assistance required for declined charge"
    (IntentType.HELP, IntentType.PAYMENT): re.compile(
        r'\b(?:help|assist).{1,30}(?:pay|payment|bill)\b',
        re.IGNORECASE
    ),
    
    # Account information requests
    # Matches: "How do I update my profile?"
    #          "What's the account deletion process?"
    (IntentType.INQUIRY, IntentType.ACCOUNT): re.compile(
        r'\b(?:what|how).{1,30}(?:account|login|password)\b',
        re.IGNORECASE
    ),
    
    # Payment information requests
    # Matches: "How do recurring payments work?"
    #          "What payment methods are accepted?"
    (IntentType.INQUIRY, IntentType.PAYMENT): re.compile(
        r'\b(?:what|how).{1,30}(?:pay|payment|bill)\b',
        re.IGNORECASE
    ),
}
