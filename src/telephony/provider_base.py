# app/src/telephony/provider_base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List


class TelephonyProvider(ABC):
    """Abstract base class for telephony service providers."""
    
    @abstractmethod
    def build_voice_response(
        self, 
        say_text: Optional[str] = None, 
        play_url: Optional[str] = None, 
        get_digits: Optional[Dict[str, Any]] = None,
        record: bool = False,
        **kwargs
    ) -> str:
        """
        Build a voice response for telephony service.
        
        Args:
            say_text: Text to be spoken
            play_url: URL of audio file to play
            get_digits: Configuration for collecting digits
            record: Whether to record the call
            **kwargs: Additional parameters for specific actions
        
        Returns:
            Response in the provider's required format (XML, JSON, etc.)
        """
        pass
    
    @abstractmethod
    def make_outbound_call(
        self, 
        to_number: str, 
        client_name: str = None, 
        say_text: str = None
    ) -> Dict[str, Any]:
        """
        Make an outbound call using the telephony provider.
        
        Args:
            to_number: The phone number to call
            client_name: Caller ID to display (if available)
            say_text: Text to be spoken when call is answered
        
        Returns:
            Call response from the provider
        """
        pass
    
    @abstractmethod
    def is_valid_webhook_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate if an incoming webhook request is authentic.
        
        Args:
            request_data: The webhook request data
            
        Returns:
            True if the request is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def parse_call_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse incoming call webhook data into a standardized format.
        
        Args:
            request_data: Raw webhook data from the provider
            
        Returns:
            Standardized call data dictionary
        """
        pass
    
    @abstractmethod
    def parse_dtmf_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DTMF (keypad input) webhook data.
        
        Args:
            request_data: Raw webhook data from the provider
            
        Returns:
            Standardized DTMF data dictionary
        """
        pass
    
    @abstractmethod
    def parse_event_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse call event webhook data.
        
        Args:
            request_data: Raw webhook data from the provider
            
        Returns:
            Standardized event data dictionary
        """
        pass
    