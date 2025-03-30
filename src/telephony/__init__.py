# app/src/telephony/__init__.py
from typing import Optional
from config import settings
from static.constants import logger
from src.telephony.provider_base import TelephonyProvider
from src.telephony.provider_factory import get_telephony_provider

# Import all provider implementations to register them
from src.telephony.integrations.at import AfricasTalkingProvider
from src.telephony.integrations.signalwire import SignalWireProvider