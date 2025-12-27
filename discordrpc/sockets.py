import socket
import os
import struct
import json
import re
import select

from loguru import logger as log

from .exceptions import DiscordNotOpened
from .constants import (
    MAX_IPC_SOCKET_NUMBER,
    SOCKET_RECEIVE_TIMEOUT_SEC,
    SOCKET_BUFFER_SIZE,
)

SOCKET_DISCONNECTED: int = -1


class UnixPipe:
    def __init__(self):
        self.socket: socket.socket = None

    def connect(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_UNIX)
        self.socket.setblocking(False)
        base_path = path = (
            os.environ.get("XDG_RUNTIME_DIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TMP")
            or os.environ.get("TEMP")
            or "/tmp"
        )
        base_path = re.sub(r"\/$", "", path) + "/discord-ipc-{0}"
        for i in range(MAX_IPC_SOCKET_NUMBER):
            path = base_path.format(i)
            try:
                self.socket.connect(path)
                break
            except FileNotFoundError:
                pass
            except (OSError, ConnectionRefusedError, PermissionError) as ex:
                log.error(
                    f"Failed to connect to socket {path}, trying next socket. {ex}"
                )
                # Skip all connection errors to try all sockets
                pass
        else:
            raise DiscordNotOpened

    def disconnect(self):
        if self.socket is None:
            return
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (OSError, AttributeError):
            pass  # Socket might already be disconnected or closed
        try:
            self.socket.close()
        except (OSError, AttributeError):
            pass  # Socket might already be closed
        self.socket = None  # Reset so connect() creates a fresh socket

    def send(self, payload, op):
        payload = json.dumps(payload).encode("UTF-8")
        payload = struct.pack("<ii", op, len(payload)) + payload
        size = 0
        while size == 0 or size < len(payload):
            res = self.socket.send(payload[size:])
            size += res

    def receive(self) -> (int, str):
        ready = select.select([self.socket], [], [], SOCKET_RECEIVE_TIMEOUT_SEC)
        if not ready[0]:
            return 0, {}
        data = self.socket.recv(SOCKET_BUFFER_SIZE)
        if len(data) == 0:
            return SOCKET_DISCONNECTED, {}
        header = data[:8]
        code = int.from_bytes(header[:4], "little")
        length = int.from_bytes(header[4:], "little")
        all_data = data[8:]
        buffer_size = length - len(all_data)
        if buffer_size < 0:
            return 0, {}
        data = self.socket.recv(length - len(all_data))
        all_data += data
        return code, all_data.decode("UTF-8")
