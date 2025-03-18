# static/constants.py
import logging
from typing import Dict, List

from src.nlp.intent_patterns import IntentType
from src.nlp.entity_extractor import EntityType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

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
