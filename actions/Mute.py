from enum import StrEnum

from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from GtkHelper.GenerativeUI.EntryRow import EntryRow

from ..discordrpc.commands import VOICE_SETTINGS_UPDATE


class Icons(StrEnum):
    MUTE = "mute"
    UNMUTE = "unmute"


class Mute(DiscordCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = False
        self._muted: bool = False
        self.icon_keys = [Icons.MUTE, Icons.UNMUTE]
        self.current_icon = self.get_icon(Icons.MUTE)
        self.icon_name = Icons.MUTE

    def on_ready(self):
        super().on_ready()
        self.plugin_base.connect_to_event(
                event_id=f"{self.plugin_base.get_plugin_id()}::{VOICE_SETTINGS_UPDATE}",
                callback=self._update_display,
                )

    def create_event_assigners(self):
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="toggle-mute",
                ui_label="toggle-mute",
                default_event=Input.Key.Events.DOWN,
                callback=self._on_toggle,
            )
        )

        self.event_manager.add_event_assigner(
            EventAssigner(
                id="enable-mute",
                ui_label="enable-mute",
                default_event=None,
                callback=self._on_mute,
            )
        )

        self.event_manager.add_event_assigner(
            EventAssigner(
                id="disable-mute",
                ui_label="disable-mute",
                default_event=None,
                callback=self._off_mute,
            )
        )

    def _on_toggle(self, _):
        try:
            self.backend.set_mute(not self._muted)
        except Exception as ex:
            log.error(ex)
            self.show_error(3)

    def _on_mute(self, _):
        try:
            self.backend.set_mute(True)
        except Exception as ex:
            log.error(ex)
            self.show_error(3)

    def _off_mute(self, _):
        try:
            self.backend.set_mute(False)
        except Exception as ex:
            log.error(ex)
            self.show_error(3)

    def _update_display(self, *args, **kwargs):
        if not self.backend:
            self.show_error()
            return
        else:
            self.hide_error()
        data = args[1]
        self._muted = data.get("mute", False)
        icon = Icons.MUTE if self._muted else Icons.UNMUTE
        self.icon_name = Icons(icon)
        self.current_icon = self.get_icon(self.icon_name)
        self.display_icon()
