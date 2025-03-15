import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("zeipo-api")

AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large"]