import socket
import os
import struct
import json
import re
import select

from loguru import logger as log

from .exceptions import DiscordNotOpened

SOCKET_DISCONNECTED: int = -1


class UnixPipe:

    def __init__(self):
        self.socket: socket.socket = None

    def connect(self):
        if self.socket is None:
            self.socket = socket.socket(socket.AF_UNIX)
        self.socket.setblocking(False)
        base_path = path = os.environ.get('XDG_RUNTIME_DIR') or os.environ.get(
            'TMPDIR') or os.environ.get('TMP') or os.environ.get('TEMP') or '/tmp'
        base_path = re.sub(r'\/$', '', path) + '/discord-ipc-{0}'
        for i in range(10):
            path = base_path.format(i)
            try:
                self.socket.connect(path)
                break
            except FileNotFoundError:
                pass
            except Exception as ex:
                log.error(
                    f"failed to connect to socket {path}, trying next socket. {ex}")
                # Skip all errors to try all sockets
                pass
        else:
            raise DiscordNotOpened

    def disconnect(self):
        if self.socket is None:
            return
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def send(self, payload, op):
        payload = json.dumps(payload).encode('UTF-8')
        payload = struct.pack('<ii', op, len(payload)) + payload
        self.socket.send(payload)

    def receive(self) -> (int, str):
        ready = select.select([self.socket], [], [], 1)
        if not ready[0]:
            return 0, {}
        data = self.socket.recv(1024)
        if len(data) == 0:
            return SOCKET_DISCONNECTED, {}
        header = data[:8]
        code = int.from_bytes(header[:4], "little")
        length = int.from_bytes(header[4:], "little")
        all_data = data[8:]
        buffer_size = length - len(all_data)
        if buffer_size < 0:
            return 0, {}
        data = self.socket.recv(length-len(all_data))
        all_data += data
        return code, all_data.decode('UTF-8')
