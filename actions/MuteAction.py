import os

from gi.repository import Gtk, Adw, Gio, GObject

from ..DiscordActionBase import DiscordActionBase
from ..discordrpc.commands import VOICE_SETTINGS_UPDATE

from loguru import logger as log


class MuteAction(DiscordActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode: str = 'Toggle'
        self.muted: bool = False
        self.label_location: str = 'Bottom'

    def on_ready(self):
        self.load_config()
        self.plugin_base.add_callback(
            VOICE_SETTINGS_UPDATE, self.update_display)
        self.plugin_base.backend.register_callback(
            VOICE_SETTINGS_UPDATE, self.update_display)

    def update_display(self, value: dict):
        self.muted = value['mute']
        image = "Discord_Mic_-_On.png"
        if self.muted:
            image = "Discord_Mic_-_Off.png"
        self.set_media(media_path=os.path.join(
            self.plugin_base.PATH, "assets", image), size=0.85)

    def on_tick(self):
        if self.muted:
            self.set_label("Muted", position=self.label_location.lower())
        else:
            self.set_label("Unmuted", position=self.label_location.lower())

    def load_config(self):
        super().load_config()
        settings = self.get_settings()
        self.mode = settings.get('mode')
        if not self.mode:
            self.mode = 'Toggle'
        self.label_location = settings.get('label_location')
        if not self.label_location:
            self.label_location = 'Bottom'

    def get_config_rows(self):
        super_rows = super().get_config_rows()

        self.action_model = Gtk.StringList()
        self.mode_row = Adw.ComboRow(
            model=self.action_model, title=self.plugin_base.lm.get("actions.mute.choice.title"))

        index = 0
        found = 0
        for k in ['Mute', 'Unmute', 'Toggle']:
            self.action_model.append(k)
            if self.mode == k:
                found = index
            index += 1
        self.mode_row.set_selected(found)
        self.mode_row.connect("notify::selected", self.on_change_mode)

        found = 0
        index = 0
        self.label_model = Gtk.StringList()
        self.label_row = Adw.ComboRow(
            model=self.label_model, title=self.plugin_base.lm.get("actions.mute.label_choice.title"))
        for k in ['Top', 'Center', 'Bottom', 'None']:
            self.label_model.append(k)
            if self.label_location == k:
                found = index
            index += 1
        self.label_row.set_selected(found)
        self.label_row.connect("notify::selected", self.on_change_label_row)

        icon_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 1)
        icon_box.set_spacing(18)
        icon_box.set_halign(Gtk.Align.CENTER)
        for title, icon in {"Mute": "Discord_Mic_-_Off.png", "Unmute": "Discord_Mic_-_On.png"}.items():
            box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 1)
            box.append(Gtk.Label.new(f"{title} Icon"))
            image = Gtk.Image.new_from_file(os.path.join(
                self.plugin_base.PATH, "assets", icon))
            image.set_pixel_size(32)
            box.append(image)
            button = Gtk.Button.new()
            button.set_child(box)
            icon_box.append(button)

        icon_row = Adw.PreferencesRow()
        icon_row.set_child(icon_box)

        super_rows.append(self.mode_row)
        super_rows.append(self.label_row)
        super_rows.append(icon_row)
        return super_rows

    def on_change_mode(self, *_):
        settings = self.get_settings()
        selected_index = self.mode_row.get_selected()
        settings['mode'] = self.action_model[selected_index].get_string()
        self.mode = settings['mode']
        self.set_settings(settings)

    def on_change_label_row(self, *_):
        self.set_label('', position=self.label_location.lower())
        settings = self.get_settings()
        selected_index = self.label_row.get_selected()
        settings['label_location'] = self.label_model[selected_index].get_string()
        self.label_location = settings['label_location']
        self.set_settings(settings)

    def on_key_down(self):
        match self.mode:
            case "Mute":
                if not self.plugin_base.backend.set_mute(True):
                    self.show_error(5)
            case "Unmute":
                if not self.plugin_base.backend.set_mute(False):
                    self.show_error(5)
            case "Toggle":
                if not self.plugin_base.backend.set_mute(not self.muted):
                    self.show_error(5)
