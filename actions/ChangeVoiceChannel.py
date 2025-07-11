from enum import StrEnum

from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from GtkHelper.GenerativeUI.EntryRow import EntryRow


class Icons(StrEnum):
    CHANGE_VOICE = ""


class ChangeVoiceChannel(DiscordCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True

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
                callback=self._on_change_channel
            )
        )

    def _on_change_channel(self, _):
        channel = self._channel_row.get_value()
        if channel != "0":
            try:
                self.backend.change_voice_channel(channel)
            except Exception as ex:
                log.error(ex)
                self.show_error(3)
        #The channel ID is 0
        else:
            try:
                self.backend.leave_voice_channel()
            except Exception as ex:
                log.error(ex)
                self.show_error(3)
            
