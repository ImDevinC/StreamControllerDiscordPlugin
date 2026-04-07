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
SOCKET_RECEIVE_TIMEOUT: int = 10


class UnixPipe:
    def __init__(self):
        log.debug("UnixPipe.__init__: Creating UnixPipe instance")
        self.socket: socket.socket = None

    def connect(self):
        log.debug(
            f"UnixPipe.connect: Starting connection, current socket={self.socket is not None}"
        )
        if self.socket is not None:
            log.debug("Socket already connected, disconnecting first.")
            self.disconnect()
        log.debug("UnixPipe.connect: Creating new AF_UNIX SOCK_STREAM socket")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(SOCKET_CONNECT_TIMEOUT)
        log.debug(f"UnixPipe.connect: Socket timeout set to {SOCKET_CONNECT_TIMEOUT}s")
        base_path = path = (
            os.environ.get("XDG_RUNTIME_DIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TMP")
            or os.environ.get("TEMP")
            or "/tmp"
        )
        log.debug(f"UnixPipe.connect: Base path from env={base_path}")
        base_path = re.sub(r"\/$", "", path) + "/discord-ipc-{0}"
        log.debug(f"UnixPipe.connect: Will try paths matching pattern: {base_path}")
        for i in range(MAX_IPC_SOCKET_RANGE):
            path = base_path.format(i)
            try:
                log.debug(f"Attempting to connect to socket at path: {path}")
                self.socket.connect(path)
                log.debug(
                    f"UnixPipe.connect: Successfully connected to socket at {path}"
                )
                break
            except FileNotFoundError:
                log.warning(f"socket {path} not found, trying next socket.")
                log.debug(
                    f"UnixPipe.connect: Socket {path} does not exist (FileNotFoundError)"
                )
                pass
            except ConnectionRefusedError as ex:
                log.debug(
                    f"UnixPipe.connect: Connection refused for {path} - Discord may not be running or socket stale"
                )
                pass
            except PermissionError as ex:
                log.debug(f"UnixPipe.connect: Permission denied for {path}")
                pass
            except Exception as ex:
                log.error(
                    f"failed to connect to socket {path}, trying next socket. {ex}"
                )
                log.debug(
                    f"UnixPipe.connect: Unexpected error for {path}: {type(ex).__name__}: {ex}"
                )
                # Skip all errors to try all sockets
                pass
        else:
            log.debug(
                f"UnixPipe.connect: Exhausted all {MAX_IPC_SOCKET_RANGE} socket paths, Discord not found"
            )
            raise DiscordNotOpened
        log.debug(f"Connected to socket at path: {path}")
        log.debug("UnixPipe.connect: Setting socket to non-blocking mode")
        self.socket.setblocking(False)
        log.debug("UnixPipe.connect: Connection setup complete")

    def disconnect(self):
        log.debug(
            f"UnixPipe.disconnect: Disconnecting, socket exists={self.socket is not None}"
        )
        if self.socket is None:
            log.debug("UnixPipe.disconnect: Socket is None, nothing to disconnect")
            return
        try:
            log.debug("UnixPipe.disconnect: Calling socket.shutdown(SHUT_RDWR)")
            self.socket.shutdown(socket.SHUT_RDWR)
            log.debug("UnixPipe.disconnect: Socket shutdown successful")
        except OSError as ex:
            # Socket might already be disconnected
            log.debug(f"Socket shutdown error (already disconnected): {ex}")
        try:
            log.debug("UnixPipe.disconnect: Calling socket.close()")
            self.socket.close()
            log.debug("UnixPipe.disconnect: Socket close successful")
        except OSError as ex:
            log.debug(f"Socket close error: {ex}")
        self.socket = None  # Reset so connect() creates a fresh socket
        log.debug("UnixPipe.disconnect: Socket set to None, disconnect complete")

    def send(self, payload, op):
        log.debug(
            f"UnixPipe.send: Sending payload with op={op}, payload_keys={list(payload.keys()) if isinstance(payload, dict) else 'not_dict'}"
        )
        payload_bytes = json.dumps(payload).encode("UTF-8")
        header = struct.pack("<ii", op, len(payload_bytes))
        message = header + payload_bytes
        log.debug(
            f"UnixPipe.send: Total message size={len(message)} bytes (header=8, payload={len(payload_bytes)})"
        )
        self.socket.settimeout(SOCKET_SEND_TIMEOUT)
        log.debug(
            f"UnixPipe.send: Socket timeout set to {SOCKET_SEND_TIMEOUT}s for send"
        )
        try:
            self.socket.sendall(message)
            log.debug(f"UnixPipe.send: Successfully sent {len(message)} bytes")
        except Exception as ex:
            log.debug(f"UnixPipe.send: Send failed with {type(ex).__name__}: {ex}")
            raise

    def receive(self) -> (int, str):
        log.debug("UnixPipe.receive: Starting receive operation")
        try:
            data = self.socket.recv(SOCKET_BUFFER_SIZE)
            log.debug(f"UnixPipe.receive: Received {len(data)} bytes from socket")
        except BlockingIOError as ex:
            log.debug(f"UnixPipe.receive: BlockingIOError (no data available): {ex}")
            raise
        except Exception as ex:
            log.debug(
                f"UnixPipe.receive: Exception during recv: {type(ex).__name__}: {ex}"
            )
            raise

        if len(data) == 0:
            log.debug("UnixPipe.receive: Received 0 bytes, socket disconnected")
            return SOCKET_DISCONNECTED, {}

        header = data[:8]
        code = int.from_bytes(header[:4], "little")
        length = int.from_bytes(header[4:], "little")
        log.debug(
            f"UnixPipe.receive: Header parsed - code={code}, declared_length={length}"
        )

        all_data = b""
        if length < 0:
            log.debug(
                f"UnixPipe.receive: Invalid negative length={length}, returning BAD_BUFFER_SIZE"
            )
            return SOCKET_BAD_BUFFER_SIZE, {}
        if length > 0:
            log.debug(f"UnixPipe.receive: Reading {length} bytes of payload data")
            try:
                data = self.socket.recv(length)
                log.debug(f"UnixPipe.receive: Read {len(data)} bytes of payload")
                all_data += data
            except Exception as ex:
                log.debug(
                    f"UnixPipe.receive: Exception reading payload: {type(ex).__name__}: {ex}"
                )
                raise

        decoded = all_data.decode("UTF-8")
        log.debug(
            f"UnixPipe.receive: Successfully decoded {len(decoded)} chars, returning code={code}"
        )
        return code, decoded
