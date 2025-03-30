# app/src/telephony/provider_factory.py
from typing import Dict, Optional
from config import settings
from static.constants import logger

from .provider_base import TelephonyProvider

# Global telephony provider instance
_telephony_provider: Optional[TelephonyProvider] = None

# Registry of available providers
_provider_registry: Dict[str, type] = {}

def register_provider(provider_name: str, provider_class: type) -> None:
    """
    Register a telephony provider implementation.
    
    Args:
        provider_name: Name to register the provider under
        provider_class: The provider class (must inherit from TelephonyProvider)
    """
    _provider_registry[provider_name] = provider_class
    logger.info(f"Registered telephony provider: {provider_name}")

def get_telephony_provider() -> TelephonyProvider:
    """
    Get the configured telephony provider instance.
    
    Returns:
        The telephony provider instance
    """
    global _telephony_provider
    
    if _telephony_provider is None:
        provider_name = get_telephony_provider_name(_telephony_provider)
        
        if provider_name not in _provider_registry:
            raise ValueError(f"Telephony provider '{provider_name}' not registered")
        
        try:
            logger.info(f"Initializing telephony provider: {provider_name}")
            provider_class = _provider_registry[provider_name]
            
            _telephony_provider = provider_class()
            logger.debug(f"Using telephony provider: {_telephony_provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Error initializing telephony provider {provider_name}: {str(e)}", exc_info=True)
            # Fall back to default provider if available
            default_provider = settings.DEFAULT_TELEPHONY_PROVIDER
            if default_provider != provider_name and default_provider in _provider_registry:
                logger.warning(f"Falling back to default provider: {default_provider}")
                provider_class = _provider_registry[default_provider]
                _telephony_provider = provider_class()
            else:
                raise
    
    return _telephony_provider

def set_telephony_provider(provider_name: str) -> TelephonyProvider:
    """Set the active telephony provider.
    
    Args:
        provider_name: Name of the telephony provider to use
        
    Returns:
        The telephony provider instance
    """
    global _telephony_provider
    
    if provider_name not in _provider_registry:
        raise ValueError(f"Telephony provider '{provider_name}' not registered")
    
    # Clean up old provider if any
    stop_telephony_provider()
    
    # Create new provider
    try:
        logger.info(f"Switching telephony provider to: {provider_name}")
        provider_class = _provider_registry[provider_name]
        _telephony_provider = provider_class()
        
        return _telephony_provider
        
    except Exception as e:
        logger.error(f"Error initializing provider {provider_name}: {str(e)}", exc_info=True)

def stop_telephony_provider() -> None:
    """Stop the current telephony provider."""
    global _telephony_provider
    
    if _telephony_provider is not None:
        try:
            logger.info(f"Stopping telephony provider: {get_telephony_provider_name(_telephony_provider)}")
            _telephony_provider.stop()
        except Exception as e:
            logger.error(f"Error stopping telephony provider: {str(e)}", exc_info=True)
        finally:
            _telephony_provider = None
            
def get_telephony_provider_name(provider: TelephonyProvider) -> str:
    """Get the name of the current telephony provider."""
    return provider.__class__.__name__