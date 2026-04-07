import uuid
import json
import threading

import requests
from loguru import logger as log

from .sockets import UnixPipe, SOCKET_BAD_BUFFER_SIZE, SOCKET_DISCONNECTED
from socket import timeout
from .commands import *
from .exceptions import *
from .constants import MAX_SOCKET_RETRY_ATTEMPTS


OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


class AsyncDiscord:
    def __init__(self, client_id: str, client_secret: str, access_token: str = ""):
        log.debug(
            f"AsyncDiscord.__init__: Creating client with client_id={client_id[:8] if client_id else 'None'}..."
        )
        self.rpc = UnixPipe()
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.polling = False
        self._session = requests.Session()  # Reuse HTTP connections
        log.debug("AsyncDiscord.__init__: Client created, UnixPipe initialized")

    def _send_rpc_command(self, command: str, args: dict = None):
        payload = {"cmd": command, "nonce": str(uuid.uuid4())}
        if args is not None:
            payload["args"] = args
        log.debug(
            f"_send_rpc_command: Sending command={command}, args_keys={list(args.keys()) if args else 'None'}"
        )
        self.rpc.send(payload, OP_FRAME)
        log.debug(f"_send_rpc_command: Command {command} sent successfully")

    def is_connected(self):
        log.debug(f"is_connected: polling={self.polling}")
        return self.polling

    def connect(self, callback: callable):
        log.debug(
            f"connect: Starting connection process with callback={callback.__name__ if hasattr(callback, '__name__') else callback}"
        )
        tries = 0
        while tries < MAX_SOCKET_RETRY_ATTEMPTS:
            try:
                log.debug(
                    f"Attempting to connect to socket, attempt {tries + 1}/{MAX_SOCKET_RETRY_ATTEMPTS}"
                )
                self.rpc.connect()
                log.debug("connect: Socket connected successfully")
                break
            except Exception as ex:
                log.error(f"failed to connect to socket. {ex}")
                log.debug(
                    f"connect: Connection attempt {tries + 1} failed with {type(ex).__name__}: {ex}"
                )
                tries += 1

        if tries >= MAX_SOCKET_RETRY_ATTEMPTS:
            log.debug(
                f"connect: All {MAX_SOCKET_RETRY_ATTEMPTS} connection attempts failed"
            )
            raise RPCException

        log.debug(
            f"connect: Sending handshake with client_id={self.client_id[:8] if self.client_id else 'None'}..."
        )
        self.rpc.send({"v": "1", "client_id": self.client_id}, OP_HANDSHAKE)
        log.debug("connect: Handshake sent, waiting for response")
        code, resp = self.rpc.receive()
        log.debug(
            f"connect: Received handshake response, code={code}, resp_length={len(resp) if resp else 0}"
        )

        if not resp:
            log.error("no response from discord client")
            log.debug("connect: Empty response from Discord client during handshake")
            raise RPCException

        if code == SOCKET_BAD_BUFFER_SIZE:
            log.error("bad buffer size when receiving data from socket")
            log.debug("connect: Bad buffer size during handshake")
            raise RPCException

        try:
            data = json.loads(resp)
            log.debug(
                f"connect: Parsed handshake response, cmd={data.get('cmd')}, evt={data.get('evt')}"
            )
        except Exception as ex:
            log.error(f"invalid response. {ex}")
            log.debug(
                f"connect: Failed to parse handshake response: {resp[:200] if resp else 'None'}"
            )
            raise RPCException
        if data.get("code") == 4000:
            log.debug("connect: Received error code 4000 (Invalid ID)")
            raise InvalidID
        if data.get("cmd") != "DISPATCH" or data.get("evt") != "READY":
            log.debug(
                f"connect: Unexpected handshake response - cmd={data.get('cmd')}, evt={data.get('evt')}, expected DISPATCH/READY"
            )
            raise RPCException
        log.debug("connect: Handshake successful, starting polling thread")
        self.polling = True
        threading.Thread(target=self.poll_callback, args=[callback]).start()
        log.debug("connect: Polling thread started, connection complete")

    def disconnect(self):
        log.debug(f"disconnect: Disconnecting, polling was={self.polling}")
        self.polling = False
        self.rpc.disconnect()
        if self._session:
            log.debug("disconnect: Closing HTTP session")
            self._session.close()
        log.debug("disconnect: Disconnection complete")

    def poll_callback(self, callback: callable):
        log.debug("poll_callback: Starting poll loop")
        while self.polling:
            try:
                val = self.rpc.receive()
                log.debug(
                    f"poll_callback: Received data, code={val[0]}, data_length={len(val[1]) if val[1] else 0}"
                )
            except timeout:
                log.debug("poll_callback: Socket timeout (normal), continuing")
                continue
            except Exception as ex:
                log.error(f"error receiving data from socket. {ex}")
                log.debug(
                    f"poll_callback: Exception in receive: {type(ex).__name__}: {ex}"
                )
                self.disconnect()
            if val[0] == SOCKET_BAD_BUFFER_SIZE:
                log.debug("bad buffer size when receiving data from socket")
            if val[0] == SOCKET_DISCONNECTED:
                log.debug("poll_callback: Socket disconnected signal received")
                self.disconnect()
            callback(val[0], val[1])
        log.debug("poll_callback: Poll loop ended, polling=False")

    def authorize(self):
        log.debug(
            f"authorize: Sending AUTHORIZE command with client_id={self.client_id[:8] if self.client_id else 'None'}..."
        )
        payload = {"client_id": self.client_id, "scopes": ["rpc", "identify"]}
        self._send_rpc_command(AUTHORIZE, payload)
        log.debug("authorize: AUTHORIZE command sent")

    def authenticate(self, access_token: str = None):
        log.debug(f"authenticate: access_token provided={bool(access_token)}")
        if not access_token:
            log.debug("authenticate: No access token, falling back to authorize()")
            self.authorize()
            return
        self.access_token = access_token
        payload = {"access_token": self.access_token}
        log.debug("authenticate: Sending AUTHENTICATE command")
        self._send_rpc_command(AUTHENTICATE, payload)
        log.debug("authenticate: AUTHENTICATE command sent")

    def refresh(self, code: str):
        log.debug(
            f"refresh: Attempting token refresh, refresh_token present={bool(code)}"
        )
        token = self._session.post(
            "https://discord.com/api/oauth2/token",
            {
                "grant_type": "refresh_token",
                "refresh_token": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=5,
        )
        log.debug(f"refresh: HTTP response status={token.status_code}")
        resp = token.json()
        if not "access_token" in resp:
            log.debug(
                f"refresh: Failed - response keys={list(resp.keys())}, error={resp.get('error')}"
            )
            raise Exception("refresh failed")
        log.debug("refresh: Token refresh successful")
        return resp

    def get_access_token(self, code: str):
        log.debug(
            f"get_access_token: Exchanging auth code, code_length={len(code) if code else 0}"
        )
        token = self._session.post(
            "https://discord.com/api/oauth2/token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=5,
        )
        log.debug(f"get_access_token: HTTP response status={token.status_code}")
        resp = token.json()
        if not "access_token" in resp:
            log.debug(
                f"get_access_token: Failed - response keys={list(resp.keys())}, error={resp.get('error')}"
            )
            raise Exception("invalid oauth request")
        log.debug("get_access_token: Token exchange successful")
        return resp

    def subscribe(self, event: str, args: dict = None):
        log.debug(f"subscribe: Subscribing to event={event}, args={args}")
        self.rpc.send(
            {"cmd": SUBSCRIBE, "evt": event, "nonce": str(uuid.uuid4()), "args": args},
            OP_FRAME,
        )
        log.debug(f"subscribe: Subscription sent for event={event}")

    def unsubscribe(self, event: str, args: dict = None):
        log.debug(f"unsubscribe: Unsubscribing from event={event}, args={args}")
        self.rpc.send(
            {
                "cmd": UNSUBSCRIBE,
                "evt": event,
                "nonce": str(uuid.uuid4()),
                "args": args,
            },
            OP_FRAME,
        )
        log.debug(f"unsubscribe: Unsubscription sent for event={event}")

    def set_voice_settings(self, settings):
        log.debug(f"set_voice_settings: Setting voice settings={settings}")
        self._send_rpc_command(SET_VOICE_SETTINGS, settings)

    def get_voice_settings(self):
        log.debug("get_voice_settings: Requesting voice settings")
        self._send_rpc_command(GET_VOICE_SETTINGS)

    def select_voice_channel(self, channel_id: str, force: bool = False):
        log.debug(
            f"select_voice_channel: Selecting channel_id={channel_id}, force={force}"
        )
        args = {"channel_id": channel_id, "force": force}
        self._send_rpc_command(SELECT_VOICE_CHANNEL, args)

    def select_text_channel(self, channel_id: str):
        log.debug(f"select_text_channel: Selecting channel_id={channel_id}")
        args = {"channel_id": channel_id}
        self._send_rpc_command(SELECT_TEXT_CHANNEL, args)

    def get_selected_voice_channel(self) -> str:
        log.debug("get_selected_voice_channel: Requesting selected voice channel")
        self._send_rpc_command(GET_SELECTED_VOICE_CHANNEL)

    def set_user_voice_settings(
        self, user_id: str, volume: int = None, mute: bool = None
    ):
        """Set voice settings for a specific user in the current voice channel.

        Args:
            user_id: The user's Discord ID (string)
            volume: Volume level 0-200 (100 = normal, 200 = 200%)
            mute: Whether to locally mute the user
        """
        log.debug(
            f"set_user_voice_settings: user_id={user_id}, volume={volume}, mute={mute}"
        )
        args = {"user_id": user_id}
        if volume is not None:
            args["volume"] = max(0, min(200, volume))
        if mute is not None:
            args["mute"] = mute
        log.debug(f"set_user_voice_settings: Sending command with args={args}")
        self._send_rpc_command(SET_USER_VOICE_SETTINGS, args)

    def get_channel(self, channel_id: str):
        """Get channel information including voice states for voice channels."""
        log.debug(f"get_channel: Requesting channel info for channel_id={channel_id}")
        self._send_rpc_command(GET_CHANNEL, {"channel_id": channel_id})
