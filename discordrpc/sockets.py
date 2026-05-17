import socket
import os
import struct
import json
import re

from loguru import logger as log

from .exceptions import DiscordNotOpened
from .constants import MAX_IPC_SOCKET_RANGE, SOCKET_RECEIVE_TIMEOUT

SOCKET_DISCONNECTED: int = -1
SOCKET_BAD_BUFFER_SIZE: int = -2
SOCKET_SEND_TIMEOUT: int = 5
SOCKET_CONNECT_TIMEOUT: int = 2


class UnixPipe:
    def __init__(self):
        self.socket: socket.socket = None

    def connect(self):
        if self.socket is not None:
            self.disconnect()

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(SOCKET_CONNECT_TIMEOUT)

        base_path = (
            os.environ.get("XDG_RUNTIME_DIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TMP")
            or os.environ.get("TEMP")
            or "/tmp"
        )

        base_path = re.sub(r"\/$", "", base_path) + "/discord-ipc-{0}"

        for i in range(MAX_IPC_SOCKET_RANGE):
            path = base_path.format(i)
            try:
                log.debug(f"Trying Discord IPC socket: {path}")
                self.socket.connect(path)
                break
            except FileNotFoundError:
                continue
            except Exception as ex:
                log.debug(f"Socket connect failed {path}: {ex}")
        else:
            raise DiscordNotOpened

        log.debug("Connected to Discord IPC socket")
        self.socket.setblocking(True)
        self.socket.settimeout(SOCKET_RECEIVE_TIMEOUT)

    def disconnect(self):
        if self.socket is None:
            return

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

        try:
            self.socket.close()
        except Exception:
            pass

        self.socket = None

    def send(self, payload, op):
        payload_bytes = json.dumps(payload).encode("utf-8")
        header = struct.pack("<ii", op, len(payload_bytes))
        message = header + payload_bytes

        orig_timeout = self.socket.gettimeout()
        try:
            self.socket.settimeout(SOCKET_SEND_TIMEOUT)
            self.socket.sendall(message)
        finally:
            self.socket.settimeout(orig_timeout)

    def receive(self) -> tuple[int | None, str | None]:
        try:
            header = self._recv_exact(8)

            code = int.from_bytes(header[:4], "little")
            length = int.from_bytes(header[4:], "little")

            if length < 0:
                return SOCKET_BAD_BUFFER_SIZE, ""

            payload = self._recv_exact(length)

            return code, payload.decode("utf-8")

        except EOFError:
            log.debug("Discord IPC connection closed or idle timeout")
            return SOCKET_DISCONNECTED, ""

        except (OSError, socket.error) as ex:
            log.error(f"Fatal socket error: {ex}")
            return SOCKET_DISCONNECTED, ""

        except Exception as ex:
            log.error(f"Unexpected receive error: {ex}")
            return SOCKET_DISCONNECTED, ""

    def _recv_exact(self, size: int):
        """Read exactly size bytes or raise EOFError."""
        data = b""

        while len(data) < size:
            try:
                chunk = self.socket.recv(size - len(data))

                # Peer closed the connection cleanly
                if not chunk:
                    raise EOFError("Discord IPC socket closed")

                data += chunk

            except socket.timeout:
                raise EOFError("Timeout during socket read - stream idle or corrupted")

            except Exception as ex:
                log.debug(f"_recv_exact socket error: {ex}")
                raise EOFError(f"Socket error during read: {ex}")

        return data
