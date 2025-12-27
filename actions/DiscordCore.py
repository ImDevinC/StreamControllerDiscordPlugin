from loguru import logger as log
from src.backend.PluginManager.ActionCore import ActionCore
from src.backend.DeckManagement.InputIdentifier import InputEvent, Input
from src.backend.PluginManager.PluginSettings.Asset import Color, Icon

from gi.repository import Gtk, Adw
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


class DiscordCore(ActionCore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Setup AssetManager values
        self.icon_keys: list[str] = []
        self.color_keys: list[str] = []
        self.current_icon: Icon = None
        self.current_color: Color = None
        self.icon_name: str = ""
        self.color_name: str = ""
        self.backend: "Backend" = self.plugin_base.backend

        self.plugin_base.asset_manager.icons.add_listener(self._icon_changed)
        self.plugin_base.asset_manager.colors.add_listener(self._color_changed)

        self.create_generative_ui()
        self.create_event_assigners()

    def on_ready(self):
        super().on_ready()
        self.display_icon()
        self.display_color()

    def create_generative_ui(self):
        pass

    def create_event_assigners(self):
        pass

    def display_icon(self):
        if not self.current_icon:
            return
        _, rendered = self.current_icon.get_values()
        if rendered:
            self.set_media(image=rendered)

    async def _icon_changed(self, event: str, key: str, asset: Icon):
        if not key in self.icon_keys:
            return
        if key != self.icon_name:
            return
        self.current_icon = asset
        self.icon_name = key
        self.display_icon()

    def display_color(self):
        if not self.current_color:
            return
        color = self.current_color.get_values()
        try:
            self.set_background_color(color)
        except (AttributeError, RuntimeError, ValueError) as ex:
            # Can occur if called too early before UI is ready
            # or if color format is invalid
            log.debug(f"Failed to set background color: {ex}")

    async def _color_changed(self, event: str, key: str, asset: Color):
        if not key in self.color_keys:
            return
        if key != self.color_name:
            return
        self.current_color = asset
        self.color_name = key
        self.display_color()
