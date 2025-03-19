# Add this to your test_api.py to debug routes
from fastapi.testclient import TestClient
from main import app

def print_app_routes():
    """Print all routes in the FastAPI app."""
    for route in app.routes:
        print(f"{route.path} [{', '.join(route.methods)}]")

# Call this function in a test case or at module level
print_app_routes()