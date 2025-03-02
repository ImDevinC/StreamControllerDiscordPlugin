from gi.repository import Gtk, Adw

from src.backend.PluginManager.ActionBase import ActionBase
from ..discordrpc.commands import VOICE_CHANNEL_SELECT
from src.backend.DeckManagement.InputIdentifier import InputEvent, Input

from loguru import logger as log


class ChangeVoiceChannelAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_channel: str = None
        self.channel_id: str = None
        self.has_configuration = True

    def on_ready(self):
        self.load_config()
        self.plugin_base.add_callback(
            VOICE_CHANNEL_SELECT, self.update_display)
        self.plugin_base.backend.register_callback(
            VOICE_CHANNEL_SELECT, self.update_display)

    def update_display(self, value: dict):
        if not self.plugin_base.backend:
            self.show_error()
            return
        else:
            self.hide_error()

    def on_tick(self):
        self.update_display({})
        if self.current_channel:
            self.set_label(self.current_channel)
        else:
            self.set_label(self.plugin_base.lm.get(
                "actions.changevoicechannel.update_channel"))

    def load_config(self):
        settings = self.get_settings()
        self.channel_id = settings.get('channel_id')

    def get_config_rows(self):
        super_rows = super().get_config_rows()

        self.channel_id_row = Adw.EntryRow(title=self.plugin_base.lm.get(
            "actions.changevoicechannel.channel_id"), text=self.channel_id)
        self.channel_id_row.connect("notify::text", self.on_change_channel_id)

        super_rows.append(self.channel_id_row)
        return super_rows

    def on_change_channel_id(self, entry, _):
        settings = self.get_settings()
        settings["channel_id"] = entry.get_text()
        self.set_settings(settings)

    def on_key_down(self):
        settings = self.get_settings()
        channel_id = settings.get('channel_id')
        self.plugin_base.backend.change_voice_channel(channel_id)

    def event_callback(self, event: InputEvent, data: dict = None):
        if event == Input.Key.Events.DOWN:
            self.on_key_down()
        if event == Input.Key.Events.HOLD_START or event == Input.Dial.Events.HOLD_START:
            self.on_key_hold_start()
        if event == Input.Dial.Events.TURN_CW:
            self.on_dial_turn(+1)
        if event == Input.Dial.Events.TURN_CCW:
            self.on_dial_turn(-1)
        if event == Input.Dial.Events.DOWN:
            self.on_dial_down()

    def on_key_hold_start(self):
        if not self.plugin_base.backend.change_voice_channel(None):
            self.show_error(5)
