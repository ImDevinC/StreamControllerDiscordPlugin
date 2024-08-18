import socket
import os
import re
import struct
import json


from loguru import logger as log

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2

HEADER_MORE_DATA = b'\x01\x00\x00\x00D\x05\x00\x00'


class RPC:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: str = None
        self.ipc = UnixPipe()
        self.setup()

    def setup(self):
        self.ipc.send({'v': 1, 'client_id': self.client_id}, op=OP_HANDSHAKE)
        resp = self.ipc.recv()
        data = json.loads(resp)

        if data.get('code') == 4000:
            raise InvalidID()
        if data.get('cmd') != 'DISPATCH' or data.get('evt') != 'READY':
            raise RPCException()

    def disconnect(self):
        self.ipc.disconnect()

    def send(self, payload):
        self.ipc.send(payload, op=OP_FRAME)
        resp = self.ipc.recv()
        return resp


class UnixPipe:
    def __init__(self):
        self.last_nonce: str = None
        self.socket = socket.socket(socket.AF_UNIX)
        base_path = path = os.environ.get('XDG_RUNTIME_DIR') or os.environ.get(
            'TMPDIR') or os.environ.get('TMP') or os.environ.get('TEMP') or '/tmp'
        base_path = re.sub(r'\/$', '', path) + '/discord-ipc-{0}'

        for i in range(10):
            path = base_path.format(i)
            log.debug("checking for discord IPC in {0}", path)
            try:
                self.socket.connect(path)
                log.debug("found discord IPD at {0}", path)
                break
            except FileNotFoundError:
                pass
        else:
            raise DiscordNotOpened()

    def recv(self):
        all_data = bytes()
        while True:
            recv_data = self.socket.recv(1024)
            log.debug(recv_data)
            log.debug(recv_data.decode('UTF-8'))
            enc_header = recv_data[:8]
            all_data = all_data + recv_data
            if enc_header == HEADER_MORE_DATA:
                self.send({'nonce': self.last_nonce}, OP_FRAME)
                continue
            break

        return all_data[8:].decode('UTF-8')

    def send(self, payload, op=OP_FRAME):
        log.debug(payload)
        self.last_nonce = payload.get('nonce')
        payload = json.dumps(payload).encode('UTF-8')
        payload = struct.pack('<ii', op, len(payload)) + payload
        self.socket.send(payload)

    def disconnect(self):
        self.send({}, OP_CLOSE)
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        self.socket = None


class RPCException(Exception):
    def __init__(self, message: str = None):
        if message is None:
            message = 'An error has occurred within DiscordRPC'
        super().__init__(message)


class DiscordNotOpened(RPCException):
    def __init__(self):
        super().__init__("Error, could not find Discord. is Discord running?")


class InvalidID(RPCException):
    def __init__(self):
        super().__init__("Invalid ID, is the ID correct? Get Application ID on https://discord.com/developers/applications")
