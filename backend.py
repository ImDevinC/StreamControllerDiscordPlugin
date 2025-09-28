import json

from streamcontroller_plugin_tools import BackendBase

from loguru import logger as log

from discordrpc import AsyncDiscord, commands


class Backend(BackendBase):
    def __init__(self):
        super().__init__()
        self.client_id: str = None
        self.client_secret: str = None
        self.access_token: str = None
        self.refresh_token: str = None
        self.discord_client: AsyncDiscord = None
        self.callbacks: dict = {}
        self._is_authed: bool = False
        self._current_voice_channel: str = None

    def discord_callback(self, code, event):
        if code == 0:
            return
        try:
            event = json.loads(event)
        except Exception as ex:
            log.error(f"failed to parse discord event: {ex}")
            return
        resp_code = event.get('data').get(
            'code', 0) if event.get('data') is not None else 0
        if resp_code in [4006, 4009]:
            if not self.refresh_token:
                self.setup_client()
                return
            try:
                token_resp = self.discord_client.refresh(self.refresh_token)
            except Exception as ex:
                log.error(f"failed to refresh token {ex}")
                self._update_tokens("", "")
                self.setup_client()
                return
            access_token = token_resp.get("access_token")
            refresh_token = token_resp.get("refresh_token")
            self._update_tokens(access_token, refresh_token)
            self.discord_client.authenticate(self.access_token)
            return
        match event.get('cmd'):
            case commands.AUTHORIZE:
                auth_code = event.get('data').get('code')
                token_resp = self.discord_client.get_access_token(
                    auth_code)
                self.access_token = token_resp.get("access_token")
                self.refresh_token = token_resp.get("refresh_token")
                self.discord_client.authenticate(self.access_token)
                self.frontend.save_access_token(self.access_token)
                self.frontend.save_refresh_token(self.refresh_token)
            case commands.AUTHENTICATE:
                self.frontend.on_auth_callback(True)
                self._is_authed = True
                for k in self.callbacks:
                    self.discord_client.subscribe(k)
                self._get_current_voice_channel()
            case commands.DISPATCH:
                evt = event.get('evt')
                self.frontend.handle_callback(evt, event.get('data'))
            case commands.GET_SELECTED_VOICE_CHANNEL:
                self._current_voice_channel = event.get('data').get(
                    'channel_id') if event.get('data') else None
                self.frontend.handle_callback(
                    commands.VOICE_CHANNEL_SELECT, event.get('data'))

    def _update_tokens(self, access_token: str = "", refresh_token: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.frontend.save_access_token(access_token)
        self.frontend.save_refresh_token(refresh_token)

    def setup_client(self):
        try:
            log.debug("new client")
            self.discord_client = AsyncDiscord(
                self.client_id, self.client_secret)
            log.debug("connect")
            self.discord_client.connect(self.discord_callback)
            if not self.access_token:
                log.debug("authorize")
                self.discord_client.authorize()
            else:
                log.debug("authenticate")
                self.discord_client.authenticate(self.access_token)
        except Exception as ex:
            self.frontend.on_auth_callback(False, str(ex))
            log.error("failed to setup discord client: {0}", ex)
            if self.discord_client:
                self.discord_client.disconnect()
            self.discord_client = None

    def update_client_credentials(self, client_id: str, client_secret: str, access_token: str = "", refresh_token: str = ""):
        if None in (client_id, client_secret) or "" in (client_id, client_secret):
            self.frontend.on_auth_callback(
                False, "actions.base.credentials.missing_client_info")
            return
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.setup_client()

    def is_authed(self) -> bool:
        return self._is_authed

    def register_callback(self, key: str, callback: callable):
        callbacks = self.callbacks.get(key, [])
        callbacks.append(callback)
        self.callbacks[key] = callbacks
        if self._is_authed:
            self.discord_client.subscribe(key)

    def set_mute(self, muted: bool):
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.set_voice_settings({'mute': muted})

    def set_deafen(self, muted: bool):
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.set_voice_settings({'deaf': muted})

    def change_voice_channel(self, channel_id: str = None) -> bool:
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.select_voice_channel(channel_id, True)

    def change_text_channel(self, channel_id: str) -> bool:
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.select_text_channel(channel_id)

    def set_push_to_talk(self, ptt: str) -> bool:
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.set_voice_settings({'mode': {"type": ptt}})

    @property
    def current_voice_channel(self):
        return self._current_voice_channel

    def _get_current_voice_channel(self):
        if self.discord_client is None or not self.discord_client.is_connected():
            self.setup_client()
        self.discord_client.get_selected_voice_channel()


backend = Backend()
