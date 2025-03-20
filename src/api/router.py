# In src/api/router.py
from fastapi import APIRouter

def create_router(prefix_path=""):
    """Create a new router with the API prefix."""
    return APIRouter(prefix=prefix_path)