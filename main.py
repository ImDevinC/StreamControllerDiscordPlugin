from src.backend.PluginManager.ActionBase import ActionBase
from src.backend.PluginManager.PluginBase import PluginBase

# Import gtk modules
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

class SampleAction(ActionBase):
    ACTION_NAME = "Sample Action"
    CONTROLS_KEY_IMAGE = False
    def __init__(self, deck_controller, page, coords):
        super().__init__(deck_controller=deck_controller, page=page, coords=coords)


class PluginTemplate(PluginBase):
    def __init__(self):
        self.PLUGIN_NAME = "PluginTemplate"
        self.GITHUB_REPO = "https://github.com/Core447/PluginTemplate"
        super().__init__()

        self.add_action(SampleAction)