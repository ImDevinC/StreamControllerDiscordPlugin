from enum import StrEnum

from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from GtkHelper.GenerativeUI.EntryRow import EntryRow

from ..discordrpc.commands import VOICE_CHANNEL_SELECT


class Icons(StrEnum):
    VOICE_CHANNEL_ACTIVE = "voice-active"
    VOICE_CHANNEL_INACTIVE = "voice-inactive"


class ChangeVoiceChannel(DiscordCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True
        self._current_channel: str = ""
        self.icon_keys = [Icons.VOICE_CHANNEL_ACTIVE, Icons.VOICE_CHANNEL_INACTIVE]
        self.current_icon = self.get_icon(Icons.VOICE_CHANNEL_INACTIVE)
        self.icon_name = Icons.VOICE_CHANNEL_INACTIVE

    def on_ready(self):
        super().on_ready()
        self.register_backend_callback(VOICE_CHANNEL_SELECT, self._update_display)

    def _update_display(self, value: dict):
        if not self.backend:
            self.show_error()
            return
        self.hide_error()
        self._current_channel = value.get("channel_id", None) if value else None
        self.icon_name = (
            Icons.VOICE_CHANNEL_INACTIVE
            if self._current_channel is None
            else Icons.VOICE_CHANNEL_ACTIVE
        )
        self.current_icon = self.get_icon(self.icon_name)
        self.display_icon()

    def create_generative_ui(self):
        self._channel_row = EntryRow(
            action_core=self,
            var_name="change_voice_channel.text",
            default_value="",
            title="change-channel-voice",
            auto_add=False,
            complex_var_name=True,
        )

    def get_config_rows(self):
        return [self._channel_row._widget]

    def create_event_assigners(self):
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="change-channel",
                ui_label="change-channel",
                default_event=Input.Key.Events.DOWN,
                callback=self._on_change_channel,
            )
        )

    def _on_change_channel(self, _):
        if self._current_channel is not None:
            try:
                self.backend.change_voice_channel(None)
            except Exception as ex:
                log.error(ex)
                self.show_error(3)
            return
        channel = self._channel_row.get_value()
        try:
            self.backend.change_voice_channel(channel)
        except Exception as ex:
            log.error(ex)
            self.show_error(3)
