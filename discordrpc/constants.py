"""Constants for Discord RPC communication."""

# Socket connection constants
MAX_SOCKET_RETRY_ATTEMPTS = 5  # Maximum number of socket connection retry attempts
MAX_IPC_SOCKET_RANGE = (
    10  # Number of IPC sockets to try (discord-ipc-0 through discord-ipc-9)
)
SOCKET_SELECT_TIMEOUT = 0.1  # Socket select timeout in seconds (reduced from 1.0s for 90% latency improvement)
#SOCKET_BUFFER_SIZE = 1024  # Socket receive buffer size in bytes
SOCKET_BUFFER_SIZE = 8
