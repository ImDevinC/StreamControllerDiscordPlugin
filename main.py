import os
import json
import threading

# Import StreamController modules
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.DeckManagement.InputIdentifier import Input
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport

# Import actions
from .settings import PluginSettings
from .actions.Mute import Mute
from .actions.Deafen import Deafen
from .actions.ChangeVoiceChannel import ChangeVoiceChannel
from .actions.ChangeTextChannel import ChangeTextChannel
from .actions.TogglePTT import TogglePTT

from loguru import logger as log


class PluginTemplate(PluginBase):
    def __init__(self):
        super().__init__(use_legacy_locale=False)
        self.callbacks = {}
        self.auth_callback_fn: callable = None
        self.lm = self.locale_manager
        self.lm.set_to_os_default()
        self._settings_manager = PluginSettings(self)
        self.has_plugin_settings = True
        self._add_icons()
        self._register_actions()
        backend_path = os.path.join(self.PATH, 'backend.py')
        self.launch_backend(backend_path=backend_path,
                            open_in_terminal=False, venv_path=os.path.join(self.PATH, '.venv'))

        try:
            with open(os.path.join(self.PATH, "manifest.json"), "r", encoding="UTF-8") as f:
                data = json.load(f)
        except Exception as ex:
            log.error(ex)
            data = {}
        app_manifest = {
            "plugin_version": data.get("version", "0.0.0"),
            "app_version": data.get("app-version", "0.0.0")
        }

        self.register(
            plugin_name="Discord",
            github_repo="https://github.com/imdevinc/StreamControllerDiscordPlugin",
            plugin_version=app_manifest.get("plugin_version"),
            app_version=app_manifest.get("app_version")
        )

        self.add_css_stylesheet(os.path.join(self.PATH, "style.css"))
        self.setup_backend()

    def _add_icons(self):
        self.add_icon("deafen", self.get_asset_path("deafen.png"))
        self.add_icon("undeafen", self.get_asset_path("undeafen.png"))
        self.add_icon("mute", self.get_asset_path("mute.png"))
        self.add_icon("unmute", self.get_asset_path("unmute.png"))
        self.add_icon("ptt", self.get_asset_path("ptt.png"))
        self.add_icon("voice", self.get_asset_path("voice_act.png"))

    def _register_actions(self):
        change_text = ActionHolder(
            plugin_base=self,
            action_base=ChangeTextChannel,
            action_id="com_imdevinc_StreamControllerDiscordPlugin::ChangeTextChannel",
            action_name="Change Text Channel",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(change_text)

        change_voice = ActionHolder(
            plugin_base=self,
            action_base=ChangeVoiceChannel,
            action_id="com_imdevinc_StreamControllerDiscordPlugin::ChangeVoiceChannel",
            action_name="Change Voice Channel",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(change_voice)

        deafen = ActionHolder(
            plugin_base=self,
            action_base=Deafen,
            action_id="com_imdevinc_StreamControllerDiscordPlugin::Deafen",
            action_name="Toggle Deafen",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(deafen)

        mute = ActionHolder(
            plugin_base=self,
            action_base=Mute,
            action_id="com_imdevinc_StreamControllerDiscordPlugin::Mute",
            action_name="Toggle Mute",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(mute)

        toggle_ptt = ActionHolder(
            plugin_base=self,
            action_base=TogglePTT,
            action_id="com_imdevinc_StreamControllerDiscordPlugin::Push_To_Talk",
            action_name="Toggle PTT",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNTESTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(toggle_ptt)

    def setup_backend(self):
        if self.backend and self.backend.is_authed():
            return
        settings = self.get_settings()
        client_id = settings.get('client_id', '')
        client_secret = settings.get('client_secret', '')
        access_token = settings.get('access_token', '')
        refresh_token = settings.get('refresh_token', '')
        threading.Thread(target=self.backend.update_client_credentials, daemon=True, args=[
            client_id, client_secret, access_token, refresh_token]).start()

    def save_access_token(self, access_token: str):
        settings = self.get_settings()
        settings['access_token'] = access_token
        self.set_settings(settings)

    def save_refresh_token(self, refresh_token: str):
        settings = self.get_settings()
        settings['refresh_token'] = refresh_token
        self.set_settings(settings)

    def add_callback(self, key: str, callback: callable):
        callbacks = self.callbacks.get(key, [])
        callbacks.append(callback)
        self.callbacks[key] = callbacks

    def handle_callback(self, key: str, data: any):
        for callback in self.callbacks.get(key):
            callback(data)

    def on_auth_callback(self, success: bool, message: str = None):
        if self.auth_callback_fn:
            self.auth_callback_fn(success, message)

    def get_settings_area(self):
        return self._settings_manager.get_settings_area()
