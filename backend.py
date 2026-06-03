import json
import threading

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
        self._is_authed: bool = False
        self._current_user_id: str = None
        self._current_voice_channel: str = None
        self._voice_channel_users: dict = {}  # {user_id: {username, nick, volume, muted}}
        self._connecting: bool = False
        self._ready: bool = False
        self._setup_lock = threading.Lock()

    def _ensure_ready(self):
        """
        Single initialization gate. Delegates to setup_client for thread safety.
        _ready means socket connected and polling started, not authenticated.
        """
        if self._ready and self.discord_client:
            return

        if not self.client_id or not self.client_secret:
            return

        # Let setup_client handle locking - don't check _connecting here
        self.setup_client()

    def setup_client(self):
        with self._setup_lock:
            # Combined check inside lock to prevent races
            if self._connecting or (self._ready and self.discord_client):
                return

            self._connecting = True

            try:
                # Cleanup old client before creating new one to prevent thread leaks
                if self.discord_client:
                    try:
                        self.discord_client.disconnect()
                    except Exception:
                        pass

                self.discord_client = AsyncDiscord(
                    self.client_id,
                    self.client_secret
                )

                self.discord_client.connect(self.discord_callback)

                if self.access_token:
                    self.discord_client.authenticate(self.access_token)
                else:
                    self.discord_client.authorize()

                # _ready = socket connected & polling. Auth tracked separately via _is_authed
                self._ready = True

            except Exception as ex:
                log.error(f"setup_client failed: {ex}")
                self.discord_client = None
                self._ready = False

            finally:
                self._connecting = False

    def update_client_credentials(
        self,
        client_id: str,
        client_secret: str,
        access_token: str = "",
        refresh_token: str = "",
    ):
        if None in (client_id, client_secret) or "" in (client_id, client_secret):
            self.frontend.on_auth_callback(
                False, "actions.base.credentials.missing_client_info"
            )
            return

        with self._setup_lock:
            self.client_id = client_id
            self.client_secret = client_secret
            self.access_token = access_token
            self.refresh_token = refresh_token
            self._ready = False
            self._is_authed = False

            if self.discord_client:
                try:
                    self.discord_client.disconnect()
                except Exception:
                    pass
                self.discord_client = None

        # setup_client acquires its own lock
        self.setup_client()

    def discord_callback(self, code, event):
        if code == 0:
            return

        if not event or not isinstance(event, str):
            return

        try:
            event = json.loads(event)
        except Exception as ex:
            log.error(f"failed to parse Discord event: {ex}")
            return

        # Handle Discord-side error codes (session invalidated)
        resp_code = (
            event.get("data").get("code", 0) if event.get("data") is not None else 0
        )
        if resp_code in [4006, 4009]:
            if not self.refresh_token:
                if self.discord_client:
                    self.discord_client.disconnect()
                self.setup_client()
                return
            try:
                token_resp = self.discord_client.refresh(self.refresh_token)
            except Exception as ex:
                log.error(f"failed to refresh token {ex}")
                self._update_tokens("", "")
                if self.discord_client:
                    self.discord_client.disconnect()
                self.setup_client()
                return
            access_token = token_resp.get("access_token")
            refresh_token = token_resp.get("refresh_token")
            self._update_tokens(access_token, refresh_token)
            self.discord_client.authenticate(self.access_token)
            return

        cmd = event.get("cmd")
        data = event.get("data") or {}

        if cmd == commands.AUTHORIZE:
            token = self.discord_client.get_access_token(data.get("code"))

            self.access_token = token.get("access_token")
            self.refresh_token = token.get("refresh_token")

            self.frontend.save_access_token(self.access_token)
            self.frontend.save_refresh_token(self.refresh_token)

            self.discord_client.authenticate(self.access_token)

        elif cmd == commands.AUTHENTICATE:
            self._is_authed = True
            self.frontend.on_auth_callback(True)

            self._current_user_id = data.get("user", {}).get("id")

            self._register_callbacks()
            self._get_current_voice_channel()

        elif cmd == commands.DISPATCH:
            self.frontend.trigger_event(event.get("evt"), data)

        elif cmd == commands.GET_SELECTED_VOICE_CHANNEL:
            self._current_voice_channel = (
                data.get("channel_id") if data else None
            )
            self.frontend.trigger_event(commands.VOICE_CHANNEL_SELECT, data)

        elif cmd == commands.GET_CHANNEL:
            self.frontend.trigger_event(commands.GET_CHANNEL, data)

        elif cmd == commands.VOICE_SETTINGS_UPDATE:
            self.frontend.trigger_event(
                commands.VOICE_SETTINGS_UPDATE,
                data
            )

    def _update_tokens(self, access_token: str = "", refresh_token: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.frontend.save_access_token(access_token)
        self.frontend.save_refresh_token(refresh_token)

    def _ensure_connected(self) -> bool:
        """Ensure client is connected, attempt reconnection if needed."""
        self._ensure_ready()

        if self.discord_client and self.discord_client.is_connected():
            return True

        # If we have credentials, attempt reconnection (setup_client handles locking)
        if self.client_id and self.client_secret:
            log.debug("Discord disconnected, attempting reconnect")
            self.setup_client()
            return self.discord_client and self.discord_client.is_connected()

        return False

    def set_mute(self, muted: bool):
        if not self._ensure_connected():
            log.warning("Cannot set mute: Discord not connected")
            return
        if not self._is_authed:
            log.warning("Cannot set mute: Discord not authenticated")
            return
        self.discord_client.set_voice_settings({"mute": bool(muted)})

    def set_deafen(self, deafened: bool):
        if not self._ensure_connected():
            log.warning("Cannot set deafen: Discord not connected")
            return
        if not self._is_authed:
            log.warning("Cannot set deafen: Discord not authenticated")
            return
        self.discord_client.set_voice_settings({"deaf": bool(deafened)})

    def is_authed(self) -> bool:
        return self._is_authed

    def _register_callbacks(self):
        self.discord_client.subscribe(commands.VOICE_SETTINGS_UPDATE)
        self.discord_client.subscribe(commands.VOICE_CHANNEL_SELECT)
        self.discord_client.subscribe(commands.GET_CHANNEL)

    def _get_current_voice_channel(self):
        if self.discord_client:
            self.discord_client.get_selected_voice_channel()

    # User volume control methods

    def set_user_volume(self, user_id: str, volume: int) -> bool:
        """Set volume for a specific user (0-200, 100 = normal)."""
        if not self._ensure_connected():
            log.warning("Cannot set user volume: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot set user volume: Discord not authenticated")
            return False
        self.discord_client.set_user_voice_settings(user_id, volume=volume)
        if user_id in self._voice_channel_users:
            self._voice_channel_users[user_id]["volume"] = volume
        return True

    def set_user_mute(self, user_id: str, muted: bool) -> bool:
        """Mute/unmute a specific user locally."""
        if not self._ensure_connected():
            log.warning("Cannot set user mute: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot set user mute: Discord not authenticated")
            return False
        self.discord_client.set_user_voice_settings(user_id, mute=muted)
        if user_id in self._voice_channel_users:
            self._voice_channel_users[user_id]["muted"] = muted
        return True

    def update_voice_channel_user(self, user_id: str, username: str, nick: str = None,
                                   volume: int = 100, muted: bool = False):
        """Track a user in the current voice channel."""
        self._voice_channel_users[user_id] = {
            "username": username,
            "nick": nick,
            "volume": volume,
            "muted": muted
        }

    def remove_voice_channel_user(self, user_id: str):
        """Remove a user from tracking when they leave."""
        self._voice_channel_users.pop(user_id, None)

    def clear_voice_channel_users(self):
        """Clear all tracked users (when leaving voice channel)."""
        self._voice_channel_users.clear()

    def get_voice_channel_users(self) -> dict:
        """Get a copy of the current voice channel users."""
        return self._voice_channel_users.copy()

    def get_channel(self, channel_id: str) -> bool:
        """Fetch channel information including voice states."""
        if not self._ensure_connected():
            log.warning("Cannot get channel: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot get channel: Discord not authenticated")
            return False
        self.discord_client.get_channel(channel_id)
        return True

    def subscribe_voice_states(self, channel_id: str) -> bool:
        """Subscribe to voice state events for a specific channel."""
        if not self._ensure_connected():
            log.warning("Cannot subscribe to voice states: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot subscribe to voice states: Discord not authenticated")
            return False
        args = {"channel_id": channel_id}
        self.discord_client.subscribe(commands.VOICE_STATE_CREATE, args)
        self.discord_client.subscribe(commands.VOICE_STATE_DELETE, args)
        self.discord_client.subscribe(commands.VOICE_STATE_UPDATE, args)
        return True

    def unsubscribe_voice_states(self, channel_id: str) -> bool:
        """Unsubscribe from voice state events for a specific channel."""
        if not self._ensure_connected():
            log.warning("Cannot unsubscribe from voice states: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot unsubscribe from voice states: Discord not authenticated")
            return False
        args = {"channel_id": channel_id}
        self.discord_client.unsubscribe(commands.VOICE_STATE_CREATE, args)
        self.discord_client.unsubscribe(commands.VOICE_STATE_DELETE, args)
        self.discord_client.unsubscribe(commands.VOICE_STATE_UPDATE, args)
        return True

    def change_voice_channel(self, channel_id: str = None) -> bool:
        if not self._ensure_connected():
            log.warning("Cannot change voice channel: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot change voice channel: Discord not authenticated")
            return False
        self.discord_client.select_voice_channel(channel_id, True)
        return True

    def change_text_channel(self, channel_id: str) -> bool:
        if not self._ensure_connected():
            log.warning("Cannot change text channel: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot change text channel: Discord not authenticated")
            return False
        self.discord_client.select_text_channel(channel_id)
        return True

    def set_push_to_talk(self, ptt: str) -> bool:
        if not self._ensure_connected():
            log.warning("Cannot set push to talk: Discord not connected")
            return False
        if not self._is_authed:
            log.warning("Cannot set push to talk: Discord not authenticated")
            return False
        self.discord_client.set_voice_settings({"mode": {"type": ptt}})
        return True

    def request_current_voice_channel(self):
        """Public method to request current voice channel state (dispatches to callbacks)."""
        self._get_current_voice_channel()

    @property
    def current_voice_channel(self):
        return self._current_voice_channel

    @property
    def current_user_id(self):
        return self._current_user_id

    def close(self):
        if self.discord_client:
            try:
                self.discord_client.disconnect()
            except Exception:
                pass

        self.discord_client = None
        self._is_authed = False
        self._ready = False


backend = Backend()
