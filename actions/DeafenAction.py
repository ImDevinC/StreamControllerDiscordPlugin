from gi.repository import Gtk, Adw

from ..DiscordActionBase import DiscordActionBase
from ..discordrpc.commands import VOICE_SETTINGS_UPDATE

from loguru import logger as log


class DeafenAction(DiscordActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode: str = None
        self.deafened: bool = False

    def on_ready(self):
        self.load_config()
        self.plugin_base.backend.register_callback(
            VOICE_SETTINGS_UPDATE, self.update_display)
        self.plugin_base.add_callback(
            VOICE_SETTINGS_UPDATE, self.update_display)

    def update_display(self, value: dict):
        self.deafened = value['deaf']

    def on_tick(self):
        if self.deafened:
            self.set_label("Deafened")
        else:
            self.set_label("Not Deafened")

    def load_config(self):
        super().load_config()
        settings = self.get_settings()
        self.mode = settings.get('mode')
        if not self.mode:
            self.mode = 'Not Deafened'

    def get_config_rows(self):
        super_rows = super().get_config_rows()
        self.action_model = Gtk.StringList()
        self.mode_row = Adw.ComboRow(
            model=self.action_model, title=self.plugin_base.lm.get("actions.deafen.choice.title"))

        index = 0
        found = 0
        for k in ['Deafen', 'Undeafen', 'Toggle']:
            self.action_model.append(k)
            if self.mode == k:
                found = index
            index += 1
        self.mode_row.set_selected(found)

        self.mode_row.connect("notify::selected", self.on_change_mode)
        super_rows.append(self.mode_row)
        return super_rows

    def on_change_mode(self, *_):
        settings = self.get_settings()
        selected_index = self.mode_row.get_selected()
        settings['mode'] = self.action_model[selected_index].get_string()
        self.mode = settings['mode']
        self.set_settings(settings)

    def on_key_down(self):
        match self.mode:
            case "Deafen":
                if not self.plugin_base.backend.set_deafen(True):
                    self.show_error()
            case "Undeafen":
                if not self.plugin_base.backend.set_deafen(False):
                    self.show_error()
            case "Toggle":
                self.plugin_base.backend.set_deafen(not self.deafened)
