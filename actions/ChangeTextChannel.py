from gi.repository import Gtk, Adw

from ..DiscordActionBase import DiscordActionBase
from ..discordrpc.commands import VOICE_CHANNEL_SELECT

from loguru import logger as log


class ChangeTextChannel(DiscordActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id: str = None

    def on_ready(self):
        self.load_config()
        self.plugin_base.add_callback(
            VOICE_CHANNEL_SELECT, self.update_display)
        self.plugin_base.backend.register_callback(
            VOICE_CHANNEL_SELECT, self.update_display)

    def update_display(self, value: dict):
        log.debug("update_display: {0}", value)

    def on_tick(self):
        pass

    def load_config(self):
        super().load_config()
        settings = self.get_settings()
        self.channel_id = settings.get('channel_id')

    def get_config_rows(self):
        super_rows = super().get_config_rows()

        self.channel_id_row = Adw.EntryRow(title=self.plugin_base.lm.get(
            "actions.changetextchannel.channel_id"), text=self.channel_id)
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
        self.plugin_base.backend.change_text_channel(channel_id)
