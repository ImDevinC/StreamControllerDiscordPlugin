"""
Constants for Discord RPC communication.
"""

# Socket connection settings
MAX_SOCKET_CONNECT_RETRIES = 5
MAX_IPC_SOCKET_NUMBER = 10  # Discord creates IPC sockets 0-9
SOCKET_RECEIVE_TIMEOUT_SEC = 0.1  # Reduced from 1.0 for better latency
SOCKET_BUFFER_SIZE = 1024

# OAuth settings
OAUTH_TOKEN_TIMEOUT_SEC = 5
