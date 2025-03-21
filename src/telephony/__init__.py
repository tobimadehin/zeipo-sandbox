# app/src/telephony/__init__.py
from typing import Optional
from config import settings
from static.constants import logger
from .provider_base import TelephonyProvider
from .provider_factory import get_telephony_provider

# Import all provider implementations to register them
from .integrations.at import AfricasTalkingProvider
from .integrations.voip_simulator import VoipSimulatorProvider