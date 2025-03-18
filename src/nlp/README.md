# Zeipo.ai NLP System

The Natural Language Processing (NLP) system provides intent recognition, entity extraction, and response generation capabilities for Zeipo.ai's AI-driven telephony solution.

## Overview

The NLP system processes transcribed speech to identify customer intents, extract relevant entities, and generate appropriate responses, optimized for low-latency telephony applications.

## Core Features

- **Regex-based Intent Recognition**: Pattern matching against predefined intent categories with confidence scoring
- **Entity Extraction**: Identifies dates, times, phone numbers, amounts, etc. from user text
- **Templated Response Generation**: Produces contextually relevant responses based on detected intents and entities
- **Database Integration**: Stores intent and entity data for analytics and historical tracking

## Architecture

The NLP system consists of five modular components:

### 1. Intent Patterns (`intent_patterns.py`)

Defines the intent types and regex patterns recognized by the system. Each intent (like GREETING, PAYMENT, HELP) has associated regex patterns that match relevant user expressions.

Key intent types include:
- GREETING: Detects hello, hi, good morning, etc.
- INQUIRY: Matches questions and information requests
- HELP: Identifies requests for assistance
- ACCOUNT: Recognizes account-related queries
- PAYMENT: Detects payment-related inquiries
- COMPLAINT: Identifies customer dissatisfaction
- CONFIRMATION/REJECTION: Detects yes/no responses

### 2. Intent Matcher (`intent_matcher.py`)

Handles the logic for matching text against intent patterns and determining confidence scores. The primary functions:

- `match_intent()`: Identifies the most likely intent and assigns a confidence score
- `identify_intents()`: Returns all possible intents above a confidence threshold

This component prioritizes compound intents (combinations like "help with payment") and considers pattern coverage for scoring.

### 3. Entity Extractor (`entity_extractor.py`)

Extracts semantic entities from text using regex patterns. Entity types include:

- DATE: Various date formats (MM/DD/YYYY, "January 1st", relative dates)
- TIME: Time expressions (HH:MM, am/pm formats)
- PHONE_NUMBER: International and local formats
- EMAIL: Standard email address format
- AMOUNT: Currency values with symbols or words
- NUMBER: Plain numerical values
- PERCENTAGE: Percentage expressions
- DURATION: Time durations (2 hours, 30 minutes)

Functions include standard extraction and position-aware extraction for highlighting within text.

### 4. Response Generator (`response_templates.py`)

Generates responses based on detected intents and entities using template selection. Features:

- Intent-specific templates with natural variations
- Entity-enhanced responses that incorporate extracted information
- Compound intent handling for complex queries
- Randomized selection for conversational variety

### 5. Intent Processor (`intent_processor.py`)

Serves as the central orchestration point, coordinating the NLP pipeline and database interactions:

- Processes incoming text from various sources
- Routes the text through intent and entity analysis
- Stores results in the database
- Returns structured results and formatted responses

## Integration Points

The NLP system integrates with other components through:

1. **API Endpoints**: Primarily through `/api/v1/nlu` for direct text processing.

2. **Africa's Talking Integration**: The voice webhook processes initial greetings and subsequent utterances.

3. **Database Models**: Uses `CallIntent`, `Intent`, and `Entity` models for persistence. 
[ [Database Models](../../db/models.py) ].

## Extending the System

### Adding New Intents

To add a new intent:
1. Add the intent to the `IntentType` enum
2. Add regex patterns to `INTENT_PATTERNS`
3. Add response templates to `RESPONSE_TEMPLATES`

### Adding New Entity Types

To add a new entity type:
1. Add the entity to the `EntityType` enum
2. Add regex patterns to `ENTITY_PATTERNS`
3. Update response enhancement logic if needed

## Performance Considerations

The NLP system is optimized for low-latency operation through:
- Fast regex-based pattern matching
- Single-pass entity extraction
- Simple template selection
- Efficient database operations

## Limitations and Future Enhancements

Current limitations:
- Limited contextual understanding compared to ML models
- Simpler entity types compared to NER systems
- Regular pattern updates needed for new expressions

Planned improvements:
- ML-based intent classification
- Named entity recognition for person names and locations
- Context-aware response generation
- Sentiment analysis
- Multilingual support

For more detailed information about the implementation of the NLP components in the NLU system, please refer to the [NLU README](../nlu/README.md).