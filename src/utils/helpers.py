import uuid
import base64

def gen_uuid_12() -> str:
    """
        Generate a 12-character UUID.
        Example: "N8hX5XK0V2vj"
    """
    # Generate a UUID4
    full_uuid = uuid.uuid4()
    # Convert to bytes and encode in base64
    b64_uuid = base64.urlsafe_b64encode(full_uuid.bytes)
    # Take first 12 characters
    return b64_uuid.decode('utf-8')[:12]

def gen_uuid_16() -> str:
    """
        Generate a 16-character UUID.
        Example: "FGhX56P0V2vj55dG"
    """
    # Generate a UUID4
    full_uuid = uuid.uuid4()
    # Convert to bytes and encode in base64
    b64_uuid = base64.urlsafe_b64encode(full_uuid.bytes)
    # Take first 12 characters
    return b64_uuid.decode('utf-8')[:16]
