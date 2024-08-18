from gi.repository import Gtk, Adw
import gi

from src.backend.PluginManager.ActionBase import ActionBase

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


class DiscordActionBase(ActionBase):
    def get_config_rows(self) -> list:
        self.status_label = Gtk.Label(
            label=self.plugin_base.lm.get("actions.base.no-credentials"))
        self.client_id = Adw.EntryRow(
            title=self.plugin_base.lm.get("actions.base.client_id"))
        self.client_secret = Adw.PasswordEntryRow(
            title=self.plugin_base.lm.get("actions.base.client_secret"))
        self.auth_button = Gtk.Button(
            label=self.plugin_base.lm.get("actions.base.validate"))
        self.auth_button.set_margin_top(10)
        self.auth_button.set_margin_bottom(10)

        self.client_id.connect("notify::text", self.on_change_client_id)
        self.client_secret.connect(
            "notify::text", self.on_change_client_secret)
        self.auth_button.connect("clicked", self.on_auth_clicked)

        group = Adw.PreferencesGroup()
        group.set_title(self.plugin_base.lm.get(
            "actions.base.credentials.title"))
        group.add(self.client_id)
        group.add(self.client_secret)
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
        client_id = settings.setdefault("client_id", "")
        client_secret = settings.setdefault("client_secret", "")
        self.client_id.set_text(client_id)
        self.client_secret.set_text(client_secret)

        self.plugin_base.set_settings(settings)

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
        self.plugin_base.backend.update_client_credentials(
            client_id, client_secret)
