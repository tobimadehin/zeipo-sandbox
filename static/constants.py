# static/constants.py
import logging
from typing import Dict, List

from colorama import Fore, Style, init
from src.nlp.intent_patterns import IntentType
from src.nlp.entity_extractor import EntityType

# Initialize colorama
init(autoreset=True)

# Custom formatter with colors
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        # Save original format
        format_orig = self._style._fmt
        
        # Add colors based on log level
        if record.levelname in self.COLORS:
            self._style._fmt = f"{self.COLORS[record.levelname]}%(asctime)s - %(name)s - %(levelname)s - %(message)s{Style.RESET_ALL}"
        
        # Format with colors
        result = super().format(record)
        
        # Restore original format
        self._style._fmt = format_orig
        
        return result

# Configure logging with colored formatter
def configure_colored_logging():
    root_logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplication
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Add console handler with colored formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)

# Usage in constants.py
configure_colored_logging()
logger = logging.getLogger("zeipo-api")

AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large"]

# Directory for storing call logs
LOG_DIR = "logs/calls"
RECORDING_DIR = "data/calls/recordings"

# Simple response templates for each intent
RESPONSE_TEMPLATES: Dict[IntentType, List[str]] = {
    IntentType.GREETING: [
        "Hello! How can I assist you today?",
        "Hi there! Welcome to our service. How may I help you?",
        "Good day! What can I do for you?",
        "Greetings! How can I be of service today?",
    ],
    
    IntentType.INQUIRY: [
        "I'd be happy to help with your inquiry. Could you please provide more details?",
        "I'll do my best to answer your question. Can you tell me more specifically what you'd like to know?",
        "Thank you for your question. Let me gather some information to better assist you.",
        "I'm here to help with your inquiry. Please share more details so I can assist you properly.",
    ],
    
    IntentType.HELP: [
        "I'm here to help. What specific assistance do you need?",
        "I'll be glad to assist you. What seems to be the problem?",
        "I'm ready to help. Please describe the issue you're facing.",
        "I'd be happy to provide support. What do you need help with today?",
    ],
    
    IntentType.ACCOUNT: [
        "I can help with your account. What would you like to know or do with your account?",
        "I have access to account information. How can I assist with your account today?",
        "For account-related inquiries, I'll need some verification. What specific information are you looking for?",
        "I'd be happy to help with your account. Please let me know what you need assistance with.",
    ],
    
    IntentType.PAYMENT: [
        "I can assist with payment-related questions. What would you like to know about your payment?",
        "I'm here to help with payment inquiries. Could you please provide more details?",
        "For payment assistance, I can provide information or process a payment. How can I help you today?",
        "I'd be happy to address your payment concern. Please share more specifics.",
    ],
    
    IntentType.COMPLAINT: [
        "I'm sorry to hear you're experiencing issues. Could you please provide more details so I can help address your concerns?",
        "I apologize for any inconvenience caused. Please share more about the problem so I can assist you better.",
        "Thank you for bringing this to our attention. I'd like to help resolve this issue. Can you please explain what happened?",
        "I understand your frustration and want to help. Could you provide more information about the problem?",
    ],
    
    IntentType.CONFIRMATION: [
        "Great! I'll proceed with that right away.",
        "Perfect! I'll take care of that for you.",
        "Excellent! I'll go ahead with that now.",
        "Thank you for confirming. I'll process that immediately.",
    ],
    
    IntentType.REJECTION: [
        "I understand. Is there something else I can help you with instead?",
        "No problem. Is there anything else you'd like assistance with?",
        "That's fine. Please let me know if you need help with something else.",
        "I understand. What would you prefer to do instead?",
    ],
    
    IntentType.GRATITUDE: [
        "You're welcome! Is there anything else I can help you with today?",
        "It's my pleasure to assist you. Don't hesitate to reach out if you need anything else.",
        "Happy to help! Is there anything else you'd like to know?",
        "Glad I could be of assistance. Let me know if you need anything else.",
    ],
    
    IntentType.FAREWELL: [
        "Thank you for contacting us. Have a wonderful day!",
        "It was a pleasure assisting you. Goodbye and take care!",
        "Thank you for your time. Have a great day ahead!",
        "Goodbye! Don't hesitate to contact us again if you need further assistance.",
    ],
    
    IntentType.UNKNOWN: [
        "I'm not quite sure I understand what you're asking. Could you please rephrase that?",
        "I apologize, but I didn't catch that. Could you please provide more details or rephrase your request?",
        "I'm having trouble understanding your request. Could you please clarify what you need help with?",
        "I'm sorry, but I'm not certain what you're asking for. Could you please elaborate?",
    ],
}

# Compound response templates (for specific combinations of intents)
COMPOUND_RESPONSE_TEMPLATES = {
    # Help with account
    (IntentType.HELP, IntentType.ACCOUNT): [
        "I'd be happy to help with your account. What specific issue are you having with your account?",
        "I can assist with account problems. Could you provide more details about the account issue?",
        "For account support, I'll need some information. What exactly do you need help with regarding your account?",
    ],
    
    # Help with payment
    (IntentType.HELP, IntentType.PAYMENT): [
        "I can help with payment-related issues. What specific problem are you experiencing with your payment?",
        "I'd be happy to assist with payment difficulties. Could you share more details about the payment issue?",
        "For payment support, I'll need to know more. What exactly do you need help with regarding your payment?",
    ],
    
    # Account inquiry
    (IntentType.INQUIRY, IntentType.ACCOUNT): [
        "I can provide information about your account. What specific details would you like to know?",
        "For account inquiries, I can help. What information are you looking for regarding your account?",
        "I'd be happy to answer questions about your account. What would you like to know specifically?",
    ],
    
    # Payment inquiry
    (IntentType.INQUIRY, IntentType.PAYMENT): [
        "I can provide information about your payment. What specific details would you like to know?",
        "For payment inquiries, I can help. What information are you looking for regarding your payment?",
        "I'd be happy to answer questions about your payment. What would you like to know specifically?",
    ],
}


# For unit testing
GREETING_TEXTS = [
    "Hello there",
    "Hi, how are you?",
    "Good morning",
    "Hey, what's up?",
    "Greetings"
]

INQUIRY_TEXTS = [
    "How do I reset my password?",
    "What is my account balance?",
    "Where can I find my transaction history?",
    "When will my subscription renew?",
    "Update credit card info",  
    "Tell me about your services"
]

PAYMENT_TEXTS = [
    "I want to pay my bill",
    "How do I make a payment?",
    "I'd like to update my payment method",
    "When is my next invoice due?",
    "What's my subscription plan?"
]

HELP_TEXTS = [
    "I need help",
    "Can you assist me?",
    "I'm having a problem",
    "Support please",
    "I need assistance with my account"
]

UNKNOWN_TEXTS = [
    "asdf qwerty",
    "1234567890",
    "...",
    "",
    None
]

COMPOUND_TEXTS = [
    ("I need help with my account", IntentType.HELP),
    ("How do I reset my account password?", IntentType.INQUIRY),
    ("Help me make a payment", IntentType.HELP),
    ("What payment methods do you accept?", IntentType.INQUIRY)
]

DATE_TEXTS = [
    "I want to schedule an appointment for 01/15/2023",
    "My payment is due on January 15, 2023",
    "The deadline is 15/01/23",
    "Let's meet next Monday",
    "I requested this yesterday"
]

TIME_TEXTS = [
    "The meeting is scheduled for 3:30pm",
    "I'll call you at 14:45",
    "Let's meet at noon",
    "The office closes at 5:00 PM",
    "My appointment is at 10.30"
]

PHONE_TEXTS = [
    "My number is +1 555-123-4567",
    "You can reach me at (555) 123-4567",
    "Call me on 08012345678",
    "My contact is +44 20 1234 5678",
    "Dial 555-123-4567"
]

EMAIL_TEXTS = [
    "My email is user@example.com",
    "Send it to test.user@domain.co.uk",
    "Contact me at first.last+tag@subdomain.example.org",
    "Email user_name@example.com with any questions",
    "support@company.africa is our helpdesk"
]

AMOUNT_TEXTS = [
    "The bill is $50.00",
    "I paid £25",
    "The item costs €19.99",
    "The fee is ₦5000",
    "My balance is 100 dollars"
]

PERCENTAGE_TEXTS = [
    "25% discount",
    "15.5 percent interest", 
    "100Percent guaranteed"
]

DURATION_TEXTS = [
    "The call lasted 5 minutes",
    "It takes 2 hours",
    "Wait for 30 seconds",
    "The project will take 3 weeks",
    "The subscription is for 1 year"
]
