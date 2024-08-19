import uuid
import json
import requests

from streamcontroller_plugin_tools import BackendBase

from loguru import logger as log

from discordrpc import AsyncDiscord, commands


class Backend(BackendBase):
    def __init__(self):
        super().__init__()
        self.client_id: str = None
        self.client_secret: str = None
        self.access_token: str = None
        self.discord_client: AsyncDiscord = None
        self.callbacks: dict = {}

    def discord_callback(self, code, event):
        log.debug("code {0}", code)
        log.debug("event {0}", event)
        if code == 0:
            return
        event = json.loads(event)
        match event.get('cmd'):
            case commands.AUTHORIZE:
                auth_code = event.get('data').get('code')
                self.access_token = self.discord_client.get_access_token(
                    auth_code)
                self.discord_client.authenticate(self.access_token)
                self.frontend.save_access_token(self.access_token)
            case commands.AUTHENTICATE:
                print("what")
                for k in self.callbacks:
                    print(f"sub to {k}")
                    self.discord_client.subscribe(k)
            case commands.DISPATCH:
                pass

    def setup_client(self):
        self.discord_client = AsyncDiscord(self.client_id, self.client_secret)
        self.discord_client.connect(self.discord_callback)
        if not self.access_token:
            self.discord_client.authorize()
        else:
            self.discord_client.authenticate(self.access_token)

    def set_mute(self, muted: bool):
        self.discord_client.set_voice_settings({'mute': muted})

    def update_client_credentials(self, client_id: str, client_secret: str, access_token: str = ""):
        if None in (client_id, client_secret) or "" in (client_id, client_secret):
            return
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.setup_client()

    def register_callback(self, key: str, callback: callable):
        if self.callbacks.get(key) is None:
            self.callbacks[key] = [callback]
            self.discord_client.subscribe(key)
        else:
            self.callbacks[key].append(callback)


backend = Backend()
