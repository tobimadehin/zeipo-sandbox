#!/usr/bin/env python3
"""
Run the Zeipo VoIP simulator server.
This script configures and starts the server optimized for VoIP testing with the mobile client.
"""
import argparse
import socket
import os
import sys
import uvicorn
import logging
from typing import List

def get_local_ip() -> str:
    """Get the local IP address that's accessible from other devices."""
    try:
        # Create a socket to determine the outgoing IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable
        s.connect(('8.8.8.8', 1))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logging.warning(f"Could not determine local IP: {str(e)}")
        return '127.0.0.1'

def get_potential_ips() -> List[str]:
    """Get a list of potential local IPs to try."""
    potential_ips = []
    
    # Try the primary outgoing IP first
    primary_ip = get_local_ip()
    if primary_ip != '127.0.0.1':
        potential_ips.append(primary_ip)
    
    # Add localhost/loopback
    potential_ips.extend(['127.0.0.1', 'localhost'])
    
    # Try to get all network interfaces
    try:
        for interface in socket.getaddrinfo(socket.gethostname(), None):
            ip = interface[4][0]
            # Only include IPv4 addresses in common private ranges
            if (ip.startswith('192.168.') or ip.startswith('10.') or 
                ip.startswith('172.16.') or ip.startswith('172.17.') or
                ip.startswith('172.18.') or ip.startswith('172.19.') or
                ip.startswith('172.2') or ip.startswith('172.3')):
                if ip not in potential_ips:
                    potential_ips.append(ip)
    except Exception as e:
        logging.warning(f"Error getting network interfaces: {str(e)}")
    
    return potential_ips

def setup_environment(host: str, port: int) -> None:
    """Set up environment variables for VoIP simulator."""
    # Configure server variables
    os.environ['BASE_URL'] = f"http://{host}:{port}"
    os.environ['WS_URL'] = f"ws://{host}:{port}/api/v1/ws"
    
    # Set telephony provider to VoIP simulator
    os.environ['TELEPHONY_PROVIDER'] = 'voip_simulator'
    os.environ['DEFAULT_TELEPHONY_PROVIDER'] = 'voip_simulator'
    
    # Enable CORS for the mobile client
    os.environ['CORS_ORIGINS'] = "*"
    
    # Enable detailed logging
    os.environ['LOG_LEVEL'] = 'DEBUG'

def main():
    parser = argparse.ArgumentParser(description='Run Zeipo VoIP Simulator Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--host', default=None, help='Host IP to bind to (default: auto-detect)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Determine host to bind to
    host = args.host or get_local_ip()
    
    # Set up environment variables
    setup_environment(host, args.port)
    
    # Print connection information
    potential_ips = get_potential_ips()
    
    print("\n=== Zeipo VoIP Simulator Server ===")
    print(f"Starting server on {host}:{args.port}")
    print("\nPotential connection URLs for your mobile client:")
    for ip in potential_ips:
        print(f"  ws://{ip}:{args.port}/api/v1/ws/audio/test_session")
    
    print("\nServer information:")
    print(f"  Web UI: http://{host}:{args.port}")
    print(f"  API docs: http://{host}:{args.port}/docs")
    print(f"  WebSocket base: ws://{host}:{args.port}/api/v1/ws")
    
    # Start uvicorn server
    uvicorn.run(
        "main:app",
        host=host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info"
    )

if __name__ == "__main__":
    main()