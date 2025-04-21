from enum import StrEnum

from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from ..discordrpc.commands import VOICE_SETTINGS_UPDATE


class ActivityMethod(StrEnum):
    VA = "VOICE_ACTIVITY"
    PTT = "PUSH_TO_TALK"


class Icons(StrEnum):
    VOICE = "voice"
    PTT = "ptt"


class TogglePTT(DiscordCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = False
        self._mode: str = ActivityMethod.PTT
        self.icon_keys = [Icons.VOICE, Icons.PTT]
        self.current_icon = self.get_icon(Icons.VOICE)
        self.icon_name = Icons.VOICE

    def on_ready(self):
        super().on_ready()
        self.plugin_base.add_callback(
            VOICE_SETTINGS_UPDATE, self._update_display)
        self.backend.register_callback(
            VOICE_SETTINGS_UPDATE, self._update_display)

    def create_event_assigners(self):
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="toggle-ptt",
                ui_label="toggle-ptt",
                default_event=Input.Key.Events.DOWN,
                callback=self._on_toggle
            )
        )

    def _on_toggle(self, _):
        new = ActivityMethod.PTT if self._mode == ActivityMethod.VA else ActivityMethod.VA
        try:
            self.backend.set_push_to_talk(str(new))
        except Exception as ex:
            log.error(ex)
            self.show_error(3)

    def _update_display(self, value: dict):
        if not self.backend:
            self.show_error()
            return
        else:
            self.hide_error()
        self._mode = value["mode"]["type"]
        icon = Icons.VOICE if self._mode == ActivityMethod.PTT else Icons.PTT
        self.icon_name = Icons(icon)
        self.current_icon = self.get_icon(self.icon_name)
        self.display_icon()
