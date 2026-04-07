import json

from streamcontroller_plugin_tools import BackendBase

from loguru import logger as log

from discordrpc import AsyncDiscord, commands


class Backend(BackendBase):
    def __init__(self):
        super().__init__()
        log.debug("Backend.__init__: Initializing Discord backend")
        self.client_id: str = None
        self.client_secret: str = None
        self.access_token: str = None
        self.refresh_token: str = None
        self.discord_client: AsyncDiscord = None
        self._is_authed: bool = False
        self._current_voice_channel: str = None
        self._is_reconnecting: bool = False
        self._voice_channel_users: dict = {}  # {user_id: {username, nick, volume, muted}}
        self._current_user_id: str = None  # Current user's ID (for filtering)
        log.debug("Backend.__init__: Initialization complete")

    def discord_callback(self, code, event):
        log.debug(f"discord_callback: Received callback with code={code}")
        if code == 0:
            log.debug("discord_callback: Code is 0, ignoring event")
            return
        try:
            event = json.loads(event)
            log.debug(
                f"discord_callback: Parsed event cmd={event.get('cmd')}, evt={event.get('evt')}"
            )
        except Exception as ex:
            log.error(f"failed to parse discord event: {ex}")
            log.debug(
                f"discord_callback: Raw event data that failed to parse: {event[:200] if isinstance(event, str) else event}"
            )
            return
        resp_code = (
            event.get("data").get("code", 0) if event.get("data") is not None else 0
        )
        log.debug(f"discord_callback: Response code from data={resp_code}")
        if resp_code in [4006, 4009]:
            log.debug(
                f"discord_callback: Got error code {resp_code}, need to refresh/reauth"
            )
            if not self.refresh_token:
                log.debug("discord_callback: No refresh token, calling setup_client()")
                self.setup_client()
                return
            try:
                log.debug("discord_callback: Attempting token refresh")
                token_resp = self.discord_client.refresh(self.refresh_token)
                log.debug("discord_callback: Token refresh successful")
            except Exception as ex:
                log.error(f"failed to refresh token {ex}")
                log.debug(
                    "discord_callback: Token refresh failed, clearing tokens and reconnecting"
                )
                self._update_tokens("", "")
                self.setup_client()
                return
            access_token = token_resp.get("access_token")
            refresh_token = token_resp.get("refresh_token")
            log.debug(
                f"discord_callback: Got new tokens, access_token present={bool(access_token)}, refresh_token present={bool(refresh_token)}"
            )
            self._update_tokens(access_token, refresh_token)
            self.discord_client.authenticate(self.access_token)
            return
        match event.get("cmd"):
            case commands.AUTHORIZE:
                log.debug("discord_callback: Processing AUTHORIZE command")
                auth_code = event.get("data").get("code")
                log.debug(
                    f"discord_callback: Got auth code, length={len(auth_code) if auth_code else 0}"
                )
                token_resp = self.discord_client.get_access_token(auth_code)
                self.access_token = token_resp.get("access_token")
                self.refresh_token = token_resp.get("refresh_token")
                log.debug(
                    f"discord_callback: Got tokens from auth, access_token present={bool(self.access_token)}"
                )
                self.discord_client.authenticate(self.access_token)
                self.frontend.save_access_token(self.access_token)
                self.frontend.save_refresh_token(self.refresh_token)
            case commands.AUTHENTICATE:
                log.debug(
                    "discord_callback: Processing AUTHENTICATE command - auth successful!"
                )
                self.frontend.on_auth_callback(True)
                self._is_authed = True
                # Capture current user ID for filtering in UserVolume
                data = event.get("data", {})
                user = data.get("user", {})
                log.debug(
                    f"discord_callback: Authenticated user={user.get('username')}, id={user.get('id')}"
                )
                self._register_callbacks()
                self._current_user_id = user.get("id")
                self._get_current_voice_channel()
            case commands.DISPATCH:
                evt = event.get("evt")
                log.debug(f"discord_callback: Processing DISPATCH event={evt}")
                self.frontend.trigger_event(evt, event.get("data"))
            case commands.GET_SELECTED_VOICE_CHANNEL:
                log.debug("discord_callback: Processing GET_SELECTED_VOICE_CHANNEL")
                self._current_voice_channel = (
                    event.get("data").get("channel_id") if event.get("data") else None
                )
                log.debug(
                    f"discord_callback: Current voice channel={self._current_voice_channel}"
                )
                self.frontend.trigger_event(
                    commands.VOICE_CHANNEL_SELECT, event.get("data")
                )
            case commands.GET_CHANNEL:
                log.debug(
                    f"discord_callback: Processing GET_CHANNEL, data keys={list(event.get('data', {}).keys()) if event.get('data') else 'None'}"
                )
                self.frontend.trigger_event(commands.GET_CHANNEL, event.get("data"))
            case _:
                log.debug(f"discord_callback: Unhandled command={event.get('cmd')}")

    def _update_tokens(self, access_token: str = "", refresh_token: str = ""):
        log.debug(
            f"_update_tokens: Updating tokens, access_token present={bool(access_token)}, refresh_token present={bool(refresh_token)}"
        )
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.frontend.save_access_token(access_token)
        self.frontend.save_refresh_token(refresh_token)

    def setup_client(self):
        log.debug(
            f"setup_client: Starting client setup, _is_reconnecting={self._is_reconnecting}"
        )
        if self._is_reconnecting:
            log.debug("Already reconnecting, skipping duplicate attempt")
            return
        try:
            self._is_reconnecting = True
            log.debug(
                f"setup_client: Creating AsyncDiscord client with client_id={self.client_id[:8] if self.client_id else 'None'}..."
            )
            self.discord_client = AsyncDiscord(self.client_id, self.client_secret)
            log.debug("setup_client: Calling discord_client.connect()")
            self.discord_client.connect(self.discord_callback)
            log.debug(
                f"setup_client: Connected, access_token present={bool(self.access_token)}"
            )
            if not self.access_token:
                log.debug("setup_client: No access token, calling authorize()")
                self.discord_client.authorize()
            else:
                log.debug("setup_client: Have access token, calling authenticate()")
                self.discord_client.authenticate(self.access_token)
        except Exception as ex:
            log.debug(
                f"setup_client: Exception during setup: {type(ex).__name__}: {ex}"
            )
            self.frontend.on_auth_callback(False, str(ex))
            log.error("failed to setup discord client: {0}", ex)
            if self.discord_client:
                log.debug("setup_client: Disconnecting failed client")
                self.discord_client.disconnect()
            self.discord_client = None
        finally:
            self._is_reconnecting = False
            log.debug(
                f"setup_client: Setup complete, client={self.discord_client is not None}"
            )

    def update_client_credentials(
        self,
        client_id: str,
        client_secret: str,
        access_token: str = "",
        refresh_token: str = "",
    ):
        log.debug(
            f"update_client_credentials: client_id present={bool(client_id)}, client_secret present={bool(client_secret)}, access_token present={bool(access_token)}, refresh_token present={bool(refresh_token)}"
        )
        if None in (client_id, client_secret) or "" in (client_id, client_secret):
            log.debug(
                "update_client_credentials: Missing client_id or client_secret, aborting"
            )
            self.frontend.on_auth_callback(
                False, "actions.base.credentials.missing_client_info"
            )
            return
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        log.debug(
            "update_client_credentials: Credentials stored, calling setup_client()"
        )
        self.setup_client()

    def is_authed(self) -> bool:
        log.debug(f"is_authed: Returning {self._is_authed}")
        return self._is_authed

    def _register_callbacks(self):
        log.debug(
            "_register_callbacks: Subscribing to VOICE_SETTINGS_UPDATE, VOICE_CHANNEL_SELECT, GET_CHANNEL"
        )
        self.discord_client.subscribe(commands.VOICE_SETTINGS_UPDATE)
        self.discord_client.subscribe(commands.VOICE_CHANNEL_SELECT)
        self.discord_client.subscribe(commands.GET_CHANNEL)
        log.debug("_register_callbacks: Subscriptions complete")

    def _ensure_connected(self) -> bool:
        """Ensure client is connected, trigger reconnection if needed."""
        is_connected = (
            self.discord_client is not None and self.discord_client.is_connected()
        )
        log.debug(
            f"_ensure_connected: client exists={self.discord_client is not None}, is_connected={is_connected}, _is_reconnecting={self._is_reconnecting}"
        )
        if not is_connected:
            if not self._is_reconnecting:
                log.debug("_ensure_connected: Not connected, triggering reconnect")
                self.setup_client()
            return False
        return True

    def set_mute(self, muted: bool):
        log.debug(f"set_mute: Setting mute={muted}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot set mute")
            return
        self.discord_client.set_voice_settings({"mute": muted})
        log.debug(f"set_mute: Command sent for mute={muted}")

    def set_deafen(self, muted: bool):
        log.debug(f"set_deafen: Setting deaf={muted}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot set deafen")
            return
        self.discord_client.set_voice_settings({"deaf": muted})
        log.debug(f"set_deafen: Command sent for deaf={muted}")

    def change_voice_channel(self, channel_id: str = None) -> bool:
        log.debug(f"change_voice_channel: Changing to channel_id={channel_id}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot change voice channel")
            return False
        self.discord_client.select_voice_channel(channel_id, True)
        log.debug(f"change_voice_channel: Command sent for channel_id={channel_id}")
        return True

    def change_text_channel(self, channel_id: str) -> bool:
        log.debug(f"change_text_channel: Changing to channel_id={channel_id}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot change text channel")
            return False
        self.discord_client.select_text_channel(channel_id)
        log.debug(f"change_text_channel: Command sent for channel_id={channel_id}")
        return True

    def set_push_to_talk(self, ptt: str) -> bool:
        log.debug(f"set_push_to_talk: Setting mode={ptt}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot set push to talk")
            return False
        self.discord_client.set_voice_settings({"mode": {"type": ptt}})
        log.debug(f"set_push_to_talk: Command sent for mode={ptt}")
        return True

    @property
    def current_voice_channel(self):
        log.debug(
            f"current_voice_channel property: Returning {self._current_voice_channel}"
        )
        return self._current_voice_channel

    @property
    def current_user_id(self):
        log.debug(f"current_user_id property: Returning {self._current_user_id}")
        return self._current_user_id

    def _get_current_voice_channel(self):
        log.debug("_get_current_voice_channel: Requesting current voice channel")
        if not self._ensure_connected():
            log.warning(
                "Discord client not connected, cannot get current voice channel"
            )
            return
        self.discord_client.get_selected_voice_channel()
        log.debug("_get_current_voice_channel: Request sent")

    def request_current_voice_channel(self):
        """Public method to request current voice channel state (dispatches to callbacks)."""
        log.debug(
            "request_current_voice_channel: Public request for voice channel state"
        )
        self._get_current_voice_channel()

    # User volume control methods

    def set_user_volume(self, user_id: str, volume: int) -> bool:
        """Set volume for a specific user (0-200, 100 = normal)."""
        log.debug(f"set_user_volume: Setting user_id={user_id} volume={volume}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot set user volume")
            return False
        self.discord_client.set_user_voice_settings(user_id, volume=volume)
        if user_id in self._voice_channel_users:
            self._voice_channel_users[user_id]["volume"] = volume
            log.debug(f"set_user_volume: Updated cached volume for user_id={user_id}")
        return True

    def set_user_mute(self, user_id: str, muted: bool) -> bool:
        """Mute/unmute a specific user locally."""
        log.debug(f"set_user_mute: Setting user_id={user_id} muted={muted}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot set user mute")
            return False
        self.discord_client.set_user_voice_settings(user_id, mute=muted)
        if user_id in self._voice_channel_users:
            self._voice_channel_users[user_id]["muted"] = muted
            log.debug(f"set_user_mute: Updated cached mute state for user_id={user_id}")
        return True

    def update_voice_channel_user(
        self,
        user_id: str,
        username: str,
        nick: str = None,
        volume: int = 100,
        muted: bool = False,
    ):
        """Track a user in the current voice channel."""
        log.debug(
            f"update_voice_channel_user: Tracking user_id={user_id}, username={username}, nick={nick}, volume={volume}, muted={muted}"
        )
        self._voice_channel_users[user_id] = {
            "username": username,
            "nick": nick,
            "volume": volume,
            "muted": muted,
        }

    def remove_voice_channel_user(self, user_id: str):
        """Remove a user from tracking when they leave."""
        log.debug(
            f"remove_voice_channel_user: Removing user_id={user_id} from tracking"
        )
        self._voice_channel_users.pop(user_id, None)

    def clear_voice_channel_users(self):
        """Clear all tracked users (when leaving voice channel)."""
        log.debug(
            f"clear_voice_channel_users: Clearing {len(self._voice_channel_users)} tracked users"
        )
        self._voice_channel_users.clear()

    def get_voice_channel_users(self) -> dict:
        """Get a copy of the current voice channel users."""
        log.debug(
            f"get_voice_channel_users: Returning {len(self._voice_channel_users)} users"
        )
        return self._voice_channel_users.copy()

    def get_channel(self, channel_id: str) -> bool:
        """Fetch channel information including voice states."""
        log.debug(f"get_channel: Fetching channel_id={channel_id}")
        if not self._ensure_connected():
            log.warning("Discord client not connected, cannot get channel")
            return False
        self.discord_client.get_channel(channel_id)
        log.debug(f"get_channel: Request sent for channel_id={channel_id}")
        return True

    def subscribe_voice_states(self, channel_id: str) -> bool:
        """Subscribe to voice state events for a specific channel."""
        log.debug(
            f"subscribe_voice_states: Subscribing to voice states for channel_id={channel_id}"
        )
        if not self._ensure_connected():
            log.warning(
                "Discord client not connected, cannot subscribe to voice states"
            )
            return False
        args = {"channel_id": channel_id}
        self.discord_client.subscribe(commands.VOICE_STATE_CREATE, args)
        self.discord_client.subscribe(commands.VOICE_STATE_DELETE, args)
        self.discord_client.subscribe(commands.VOICE_STATE_UPDATE, args)
        log.debug(
            f"subscribe_voice_states: Subscribed to CREATE/DELETE/UPDATE for channel_id={channel_id}"
        )
        return True

    def unsubscribe_voice_states(self, channel_id: str) -> bool:
        """Unsubscribe from voice state events for a specific channel."""
        log.debug(
            f"unsubscribe_voice_states: Unsubscribing from voice states for channel_id={channel_id}"
        )
        if not self._ensure_connected():
            log.debug("unsubscribe_voice_states: Client not connected, returning False")
            return False
        args = {"channel_id": channel_id}
        self.discord_client.unsubscribe(commands.VOICE_STATE_CREATE, args)
        self.discord_client.unsubscribe(commands.VOICE_STATE_DELETE, args)
        self.discord_client.unsubscribe(commands.VOICE_STATE_UPDATE, args)
        log.debug(
            f"unsubscribe_voice_states: Unsubscribed from CREATE/DELETE/UPDATE for channel_id={channel_id}"
        )
        return True

    def close(self):
        log.debug(
            f"close: Closing backend, client exists={self.discord_client is not None}"
        )
        if self.discord_client:
            try:
                log.debug("close: Disconnecting Discord client")
                self.discord_client.disconnect()
            except Exception as ex:
                log.error(f"Error disconnecting Discord client: {ex}")
            self.discord_client = None
        self._is_authed = False
        log.debug("close: Backend closed")


backend = Backend()
