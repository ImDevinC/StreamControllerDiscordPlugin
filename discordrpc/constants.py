"""Constants for Discord RPC communication."""

# Socket connection constants
MAX_SOCKET_RETRY_ATTEMPTS = 5  # Maximum number of socket connection retry attempts
MAX_IPC_SOCKET_RANGE = (
    10  # Number of IPC sockets to try (discord-ipc-0 through discord-ipc-9)
)
SOCKET_RECEIVE_TIMEOUT = 0.5
