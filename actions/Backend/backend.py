from streamcontroller_plugin_tools import BackendBase

import Pyro5.api

import time
import random

@Pyro5.api.expose
class Backend(BackendBase):
    def __init__(self):
        super().__init__()

    def get_number(self):
        return str(random.randint(0, 42))

if __name__ == "__main__":
    backend = Backend()