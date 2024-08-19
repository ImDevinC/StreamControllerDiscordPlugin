import uuid
import json

from .sockets import UnixPipe
from .commands import *
from .exceptions import *
from .utils import remove_empty

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


class Discord:
    def __init__(self, client_id: str, client_secret: str):
        self.rpc = UnixPipe()
        self.client_id = client_id
        self.client_secret = client_secret

    def connect(self):
        self.rpc.connect()
        self.rpc.send({'v': 1, 'client_id': self.client_id}, OP_HANDSHAKE)
        _, resp = self.rpc.receive()
        data = json.loads(resp)
        if data.get('code') == 4000:
            raise InvalidID
        if data.get('cmd') != 'DISPATCH' or data.get('evt') != 'READY':
            raise RPCException

    def disconnect(self):
        self.rpc.disconnect()

    def authenticate(self, access_token: str):
        payload = {
            'access_token': access_token
        }
        self._send_rpc_command(AUTHENTICATE, payload)

    def _send_rpc_command(self, command: str, args: dict = None):
        payload = {
            'cmd': command,
            'nonce': str(uuid.uuid4())
        }
        if args is not None:
            payload['args'] = args
        self.rpc.send(payload, OP_FRAME)
        code, resp = self.rpc.receive()
        return resp

    def get_voice_settings(self):
        return json.loads(self._send_rpc_command(GET_VOICE_SETTINGS))

    def set_voice_settings(self, settings: dict):
        payload = remove_empty(settings)
        self._send_rpc_command(SET_VOICE_SETTINGS, payload)
