import uuid
import json
import threading

import requests
from loguru import logger as log

from .sockets import UnixPipe
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
        self.rpc = UnixPipe()
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.polling = False
        self._session = requests.Session()  # Reuse HTTP connections

    def _send_rpc_command(self, command: str, args: dict = None):
        payload = {"cmd": command, "nonce": str(uuid.uuid4())}
        if args is not None:
            payload["args"] = args
        self.rpc.send(payload, OP_FRAME)

    def is_connected(self):
        return self.polling

    def connect(self, callback: callable):
        tries = 0
        while tries < MAX_SOCKET_RETRY_ATTEMPTS:
            log.debug(
                f"Attempting to connect to socket, attempt {tries + 1}/{MAX_SOCKET_RETRY_ATTEMPTS}"
            )
            self.rpc.connect()
            self.rpc.send({"v": 1, "client_id": self.client_id}, OP_HANDSHAKE)
            _, resp = self.rpc.receive()
            if resp:
                break
            tries += 1
        try:
            data = json.loads(resp)
        except Exception as ex:
            log.error(f"invalid response. {ex}")
            raise RPCException
        if data.get("code") == 4000:
            raise InvalidID
        if data.get("cmd") != "DISPATCH" or data.get("evt") != "READY":
            raise RPCException
        self.polling = True
        threading.Thread(target=self.poll_callback, args=[callback]).start()

    def disconnect(self):
        self.polling = False
        self.rpc.disconnect()
        if self._session:
            self._session.close()

    def poll_callback(self, callback: callable):
        while self.polling:
            try:
                val = self.rpc.receive()
            except Exception as ex:
                log.error(f"error receiving data from socket. {ex}")
                self.disconnect()
                return
            if val[0] == -1:
                self.disconnect()
            callback(val[0], val[1])

    def authorize(self):
        payload = {"client_id": self.client_id, "scopes": ["rpc", "identify"]}
        self._send_rpc_command(AUTHORIZE, payload)

    def authenticate(self, access_token: str = None):
        if not access_token:
            self.authorize()
            return
        self.access_token = access_token
        payload = {"access_token": self.access_token}
        self._send_rpc_command(AUTHENTICATE, payload)

    def refresh(self, code: str):
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
        resp = token.json()
        if not "access_token" in resp:
            raise Exception("refresh failed")
        return resp

    def get_access_token(self, code: str):
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
        resp = token.json()
        if not "access_token" in resp:
            raise Exception("invalid oauth request")
        return resp

    def subscribe(self, event: str, args: dict = None):
        self.rpc.send(
            {"cmd": SUBSCRIBE, "evt": event, "nonce": str(uuid.uuid4()), "args": args},
            OP_FRAME,
        )

    def unsubscribe(self, event: str, args: dict = None):
        self.rpc.send(
            {
                "cmd": UNSUBSCRIBE,
                "evt": event,
                "nonce": str(uuid.uuid4()),
                "args": args,
            },
            OP_FRAME,
        )

    def set_voice_settings(self, settings):
        self._send_rpc_command(SET_VOICE_SETTINGS, settings)

    def get_voice_settings(self):
        self._send_rpc_command(GET_VOICE_SETTINGS)

    def select_voice_channel(self, channel_id: str, force: bool = False):
        args = {"channel_id": channel_id, "force": force}
        self._send_rpc_command(SELECT_VOICE_CHANNEL, args)

    def select_text_channel(self, channel_id: str):
        args = {"channel_id": channel_id}
        self._send_rpc_command(SELECT_TEXT_CHANNEL, args)

    def get_selected_voice_channel(self) -> str:
        self._send_rpc_command(GET_SELECTED_VOICE_CHANNEL)
