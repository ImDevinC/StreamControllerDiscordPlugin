import socket
import os
import struct
import json
import re
import select

from loguru import logger as log

from .exceptions import DiscordNotOpened
from .constants import MAX_IPC_SOCKET_RANGE, SOCKET_SELECT_TIMEOUT, SOCKET_BUFFER_SIZE

SOCKET_DISCONNECTED: int = -1
SOCKET_BAD_BUFFER_SIZE: int = -2
SOCKET_SEND_TIMEOUT: int = 5
SOCKET_CONNECT_TIMEOUT: int = 2
SOCKET_RECEIVE_TIMEOUT: int = 5

class UnixPipe:
    def __init__(self):
        self.socket: socket.socket = None

    def connect(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(SOCKET_CONNECT_TIMEOUT)
        base_path = path = (
            os.environ.get("XDG_RUNTIME_DIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TMP")
            or os.environ.get("TEMP")
            or "/tmp"
        )
        base_path = re.sub(r"\/$", "", path) + "/discord-ipc-{0}"
        for i in range(MAX_IPC_SOCKET_RANGE):
            path = base_path.format(i)
            try:
                self.socket.connect(path)
                break
            except FileNotFoundError:
                pass
            except Exception as ex:
                log.error(
                    f"failed to connect to socket {path}, trying next socket. {ex}"
                )
                # Skip all errors to try all sockets
                pass
        else:
            raise DiscordNotOpened
        self.socket.setblocking(False)

    def disconnect(self):
        if self.socket is None:
            return
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError as ex:
            # Socket might already be disconnected
            log.debug(f"Socket shutdown error (already disconnected): {ex}")
        try:
            self.socket.close()
        except OSError as ex:
            log.debug(f"Socket close error: {ex}")
        self.socket = None  # Reset so connect() creates a fresh socket

    def send(self, payload, op):
        log.debug(f"Sending payload: {payload} with op: {op}")
        payload_bytes = json.dumps(payload).encode("UTF-8")
        header = struct.pack("<ii", op, len(payload_bytes))
        message = header + payload_bytes
        self.socket.settimeout(SOCKET_SEND_TIMEOUT)
        self.socket.sendall(message)

    def receive(self) -> (int, str):
        self.socket.settimeout(SOCKET_RECEIVE_TIMEOUT)
        data = self.socket.recv(SOCKET_BUFFER_SIZE)
        if len(data) == 0:
            return SOCKET_DISCONNECTED, {}
        header = data[:8]
        code = int.from_bytes(header[:4], "little")
        length = int.from_bytes(header[4:], "little")
        all_data = data[8:]
        buffer_size = length - len(all_data)
        if buffer_size < 0:
            return SOCKET_BAD_BUFFER_SIZE, {}
        data = self.socket.recv(length - len(all_data))
        all_data += data
        return code, all_data.decode("UTF-8")
