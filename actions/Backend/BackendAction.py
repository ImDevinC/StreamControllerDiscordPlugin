from src.backend.PluginManager.ActionBase import ActionBase

import os
import Pyro5.api

@Pyro5.api.expose
class BackendAction(ActionBase):
    ACTION_NAME = "Backend Action"
    def __init__(self, deck_controller, page, coords):
        super().__init__(deck_controller=deck_controller, page=page, coords=coords)

        # Launch backend (optional)
        backend_path = os.path.join(os.path.dirname(__file__), "backend.py")
        self.launch_backend(backend_path=backend_path)

    def on_key_down(self):
        self.set_bottom_label(self.backend.get_number())