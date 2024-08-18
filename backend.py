import uuid
import json
import requests

from streamcontroller_plugin_tools import BackendBase

from loguru import logger as log

from rpc import RPC


class Backend(BackendBase):
    def __init__(self):
        super().__init__()
        self.client_id: str = None
        self.client_secret: str = None
        self.access_token: str = None
        self.rpc: RPC = None

    def send_rpc_command(self, command, msg=None):
        if self.rpc is None:
            self.rpc = RPC(self.client_id, self.client_secret)

        if self.rpc is None:
            raise Exception("not started")

        payload = {
            'cmd': command,
            'nonce': str(uuid.uuid4()),
        }
        if msg:
            payload['args'] = msg
        return self.rpc.send(payload)

    def set_mute(self, muted: bool):
        payload = {
            'mute': muted
        }
        self.send_rpc_command('SET_VOICE_SETTINGS', payload)

    def get_voice_settings(self):
        resp = self.send_rpc_command('GET_VOICE_SETTINGS')
        print(resp)

    def update_client_credentials(self, client_id: str, client_secret: str, access_token: str = ""):
        if None in (client_id, client_secret) or "" in (client_id, client_secret):
            return
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        try:
            self.rpc = RPC(client_id, client_secret)
        except Exception as ex:
            log.error(ex)
        self.authenticate_rpc()

    def authenticate_rpc(self):
        if not self.access_token:
            self.authorize()
        self.authenticate()

    def authenticate(self):
        payload = {
            'access_token': self.access_token
        }
        self.send_rpc_command('AUTHENTICATE', payload)

    def authorize(self):
        payload = {
            'client_id': self.client_id,
            'scopes': ['rpc', 'identify']
        }
        resp = self.send_rpc_command('AUTHORIZE', payload)
        data = json.loads(resp)
        if not data.get('data') or not data.get('data').get('code'):
            raise Exception("invalid auth")
        code = data.get('data').get('code')
        token = requests.post('https://discord.com/api/oauth2/token', {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        })
        resp = token.json()
        if not 'access_token' in resp:
            raise Exception("invalid oauth request")
        self.access_token = resp.get('access_token')
        self.frontend.save_access_token(self.access_token)


backend = Backend()
