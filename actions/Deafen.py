from enum import StrEnum

from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from GtkHelper.GenerativeUI.EntryRow import EntryRow

from ..discordrpc.commands import VOICE_SETTINGS_UPDATE


class Icons(StrEnum):
    DEAFEN = "deafen"
    UNDEAFEN = "undeafen"


class Deafen(DiscordCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = False
        self._deafened: bool = False
        self.icon_keys = [Icons.DEAFEN, Icons.UNDEAFEN]
        self.current_icon = self.get_icon(Icons.DEAFEN)
        self.icon_name = Icons.DEAFEN

    def on_ready(self):
        super().on_ready()
        self.backend.register_callback(
            VOICE_SETTINGS_UPDATE, self._update_display)

    def create_event_assigners(self):
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="toggle-deafen",
                ui_label="toggle-deafen",
                default_event=Input.Key.Events.DOWN,
                callback=self._on_toggle,
            )
        )

    def _on_toggle(self, _):
        try:
            self.backend.set_deafen(not self._deafened)
        except Exception as ex:
            log.error(ex)
            self.show_error(3)

    def _update_display(self, value: dict):
        if not self.backend:
            self.show_error()
            return
        else:
            self.hide_error()
        self._deafened = value["deaf"]
        icon = Icons.DEAFEN if self._deafened else Icons.UNDEAFEN
        self.icon_name = Icons(icon)
        self.current_icon = self.get_icon(self.icon_name)
        self.display_icon()
