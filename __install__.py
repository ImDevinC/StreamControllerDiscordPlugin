from streamcontroller_plugin_tools.installation_helpers import create_venv
from os.path import join, abspath, dirname

toplevel = dirname(abspath(__file__))
create_venv(path=join(toplevel, ".venv"), path_to_requirements_txt=join(toplevel, "requirements.txt"))