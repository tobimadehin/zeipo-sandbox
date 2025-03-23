import uuid
import base64
import io
from pydub import AudioSegment

from static.constants import logger

def gen_uuid_12() -> str:
    """
        Generate a 12-character UUID.
        Example: "N8hX5XK0V2vj"
    """
    # Generate a UUID4
    full_uuid = uuid.uuid4()
    # Convert to bytes and encode in base64
    b64_uuid = base64.urlsafe_b64encode(full_uuid.bytes)
    # Take first 12 alphanumeric characters
    return ''.join(c for c in b64_uuid.decode('utf-8') if c.isalnum())[:12]
def gen_uuid_16() -> str:
    """
        Generate a 16-character UUID.
        Example: "FGhX56P0V2vj55dG"
    """
    # Generate a UUID4
    full_uuid = uuid.uuid4()
    # Convert to bytes and encode in base64
    b64_uuid = base64.urlsafe_b64encode(full_uuid.bytes)
    # Take first 16 alphanumeric characters
    return ''.join(c for c in b64_uuid.decode('utf-8') if c.isalnum())[:16]

def convert_opus_to_pcm(opus_data):
    """Convert opus to pcm audio format"""
    # Load WebM/Opus data
    audio = AudioSegment.from_file(io.BytesIO(opus_data), format="webm")
    # Convert to 16kHz mono PCM
    audio = audio.set_frame_rate(16000).set_channels(1)
    # Export as raw PCM
    pcm_io = io.BytesIO()
    audio.export(pcm_io, format="s16le", codec="pcm_s16le")
    result = pcm_io.getvalue()
    logger.debug(f"Converted Opus to PCM: {len(result)} bytes")
    return result
