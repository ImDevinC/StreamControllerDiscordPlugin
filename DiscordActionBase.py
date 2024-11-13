from loguru import logger as log
from gi.repository import Gtk, Adw
import gi
import threading

from src.backend.PluginManager.ActionBase import ActionBase

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


class DiscordActionBase(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_id: str = ""
        self.client_secret: str = ""

    def get_config_rows(self) -> list:
        authed = self.plugin_base.backend.is_authed()
        if not authed:
            label = "actions.base.credentials.no-credentials"
            css_style = "discord-controller-red"
        else:
            label = "actions.base.credentials.authenticated"
            css_style = "discord-controller-green"

        self.status_label = Gtk.Label(
            label=self.plugin_base.lm.get(label), css_classes=[css_style])
        self.client_id_row = Adw.EntryRow(
            title=self.plugin_base.lm.get("actions.base.client_id"), text=self.client_id)
        self.client_secret_row = Adw.PasswordEntryRow(
            title=self.plugin_base.lm.get("actions.base.client_secret"), text=self.client_secret)
        self.auth_button = Gtk.Button(
            label=self.plugin_base.lm.get("actions.base.validate"))
        self.auth_button.set_margin_top(10)
        self.auth_button.set_margin_bottom(10)

        self.client_id_row.connect("notify::text", self.on_change_client_id)
        self.client_secret_row.connect(
            "notify::text", self.on_change_client_secret)
        self.auth_button.connect("clicked", self.on_auth_clicked)

        group = Adw.PreferencesGroup()
        group.set_title(self.plugin_base.lm.get(
            "actions.base.credentials.title"))
        group.add(self.client_id_row)
        group.add(self.client_secret_row)
        group.add(self.status_label)
        group.add(self.auth_button)

        self.load_config()
        return [group]

    def get_custom_config_area(self):
        label = Gtk.Label(
            use_markup=True,
            label=f"{self.plugin_base.lm.get('actions.info.link.label')} <a href=\"https://github.com/ImDevinC/StreamControllerDiscordPlugin\">{self.plugin_base.lm.get('actions.info.link.text')}</a>"
        )
        return label

    def load_config(self):
        settings = self.plugin_base.get_settings()
        self.client_id = settings.setdefault("client_id", "")
        self.client_secret = settings.setdefault("client_secret", "")

    def update_settings(self, key, value):
        settings = self.plugin_base.get_settings()
        settings[key] = value
        self.plugin_base.set_settings(settings)

    def on_change_client_id(self, entry, _):
        self.update_settings("client_id", entry.get_text())

    def on_change_client_secret(self, entry, _):
        self.update_settings("client_secret", entry.get_text())

    def on_auth_clicked(self, _):
        settings = self.plugin_base.get_settings()
        client_id = settings.get('client_id')
        client_secret = settings.get('client_secret')
        self.auth_button.set_sensitive(False)
        self.plugin_base.auth_callback_fn = self.on_auth_completed
        threading.Thread(target=self.plugin_base.backend.update_client_credentials, daemon=True,
                         name="update_client_credentials", args=[client_id, client_secret]).start()

    def _set_status(self, message: str, is_error: bool = False):
        self.status_label.set_label(message)
        if is_error:
            self.status_label.remove_css_class("discord-controller-green")
            self.status_label.add_css_class("discord-controller-red")
        else:
            self.status_label.remove_css_class("discord-controller-red")
            self.status_label.add_css_class("discord-controller-green")

    def on_auth_completed(self, success: bool, message: str = None):
        self.auth_button.set_sensitive(True)
        if success:
            self._set_status(self.plugin_base.lm.get(
                "actions.base.credentials.authenticated"), False)
        else:
            if self.plugin_base.lm.get(message):
                message = self.plugin_base.lm.get(message)
            elif not message:
                message = self.plugin_base.lm.get(
                    "actions.base.credentials.failed")
            self._set_status(message, True)
