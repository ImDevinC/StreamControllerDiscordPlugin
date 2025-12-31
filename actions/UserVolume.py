from loguru import logger as log

from .DiscordCore import DiscordCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.PluginManager.InputBases import Input

from ..discordrpc.commands import (
    VOICE_STATE_CREATE,
    VOICE_STATE_DELETE,
    VOICE_STATE_UPDATE,
    VOICE_CHANNEL_SELECT,
    GET_CHANNEL,
)


class UserVolume(DiscordCore):
    """Action for controlling per-user volume via dial.

    Dial behavior:
    - Rotate: Adjust volume of selected user (+/- 5% per tick)
    - Press: Cycle to next user in voice channel

    Display:
    - Top label: Current voice channel name (or "Not in voice")
    - Center label: Username/nick
    - Bottom label: Volume percentage
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = False

        # Current state
        self._users: list = []  # List of user dicts [{id, username, nick, volume, muted}, ...]
        self._current_user_index: int = 0
        self._current_channel_id: str = None
        self._current_channel_name: str = ""
        self._in_voice_channel: bool = False

        # Volume adjustment step (percentage points per dial tick)
        self.VOLUME_STEP = 5

    def on_ready(self):
        super().on_ready()

        # Subscribe to voice channel changes (doesn't need channel_id)
        self.register_backend_callback(VOICE_CHANNEL_SELECT, self._on_voice_channel_select)

        # Subscribe to GET_CHANNEL responses
        self.register_backend_callback(GET_CHANNEL, self._on_get_channel)

        # Initialize display
        self._update_display()

        # Request current voice channel state (in case we're already in a channel)
        self.backend.request_current_voice_channel()

    def create_event_assigners(self):
        # Dial rotation: adjust volume
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="volume-up",
                ui_label="volume-up",
                default_event=Input.Dial.Events.TURN_CW,
                callback=self._on_volume_up,
            )
        )
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="volume-down",
                ui_label="volume-down",
                default_event=Input.Dial.Events.TURN_CCW,
                callback=self._on_volume_down,
            )
        )

        # Dial press: cycle user
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="cycle-user",
                ui_label="cycle-user",
                default_event=Input.Dial.Events.DOWN,
                callback=self._on_cycle_user,
            )
        )

        # Also support key press for cycling (for key-based assignment)
        self.event_manager.add_event_assigner(
            EventAssigner(
                id="cycle-user-key",
                ui_label="cycle-user-key",
                default_event=Input.Key.Events.DOWN,
                callback=self._on_cycle_user,
            )
        )

    # === Event Handlers ===

    def _on_volume_up(self, _):
        """Increase current user's volume."""
        self._adjust_volume(self.VOLUME_STEP)

    def _on_volume_down(self, _):
        """Decrease current user's volume."""
        self._adjust_volume(-self.VOLUME_STEP)

    def _on_cycle_user(self, _):
        """Cycle to next user in voice channel."""
        if not self._users:
            return
        self._current_user_index = (self._current_user_index + 1) % len(self._users)
        self._update_display()

    def _adjust_volume(self, delta: int):
        """Adjust current user's volume by delta."""
        if not self._users or self._current_user_index >= len(self._users):
            return

        user = self._users[self._current_user_index]
        current_volume = user.get("volume", 100)
        new_volume = max(0, min(200, current_volume + delta))

        try:
            if self.backend.set_user_volume(user["id"], new_volume):
                user["volume"] = new_volume
                self._update_display()
        except Exception as ex:
            log.error(f"Failed to set user volume: {ex}")
            self.show_error(3)

    # === Discord Event Callbacks ===

    def _on_voice_channel_select(self, data: dict):
        """Handle user joining/leaving voice channel."""
        try:
            if data is None or data.get("channel_id") is None:
                # Left voice channel - unsubscribe from previous channel
                if self._current_channel_id:
                    self.backend.unsubscribe_voice_states(self._current_channel_id)
                self._in_voice_channel = False
                self._current_channel_id = None
                self._current_channel_name = ""
                self._users.clear()
                self._current_user_index = 0
                self.backend.clear_voice_channel_users()
            else:
                # Joined voice channel
                new_channel_id = data.get("channel_id")

                # If switching channels, unsubscribe from old channel first
                if self._current_channel_id and self._current_channel_id != new_channel_id:
                    self.backend.unsubscribe_voice_states(self._current_channel_id)
                    self._users.clear()
                    self._current_user_index = 0

                self._in_voice_channel = True
                self._current_channel_id = new_channel_id
                self._current_channel_name = data.get("name", "Voice")

                # Register frontend callbacks for voice state events
                self.plugin_base.add_callback(VOICE_STATE_CREATE, self._on_voice_state_create)
                self.plugin_base.add_callback(VOICE_STATE_DELETE, self._on_voice_state_delete)
                self.plugin_base.add_callback(VOICE_STATE_UPDATE, self._on_voice_state_update)

                # Subscribe to voice state events via backend (with channel_id)
                self.backend.subscribe_voice_states(self._current_channel_id)

                # Fetch initial user list
                self.backend.get_channel(self._current_channel_id)

            self._update_display()
        except Exception as ex:
            log.error(f"UserVolume[{id(self)}]: Error in _on_voice_channel_select: {ex}")

    def _on_get_channel(self, data: dict):
        """Handle GET_CHANNEL response with initial user list."""
        if not data:
            return

        # Check if this is for our current channel
        channel_id = data.get("id")
        if channel_id != self._current_channel_id:
            return

        # Update channel name if available
        if data.get("name"):
            self._current_channel_name = data.get("name")

        # Process voice_states array
        voice_states = data.get("voice_states", [])
        current_user_id = self.backend.current_user_id

        for vs in voice_states:
            user_data = vs.get("user", {})
            user_id = user_data.get("id")

            if not user_id:
                continue

            # Filter out self
            if user_id == current_user_id:
                continue

            user_info = {
                "id": user_id,
                "username": user_data.get("username", "Unknown"),
                "nick": vs.get("nick"),
                "volume": vs.get("volume", 100),
                "muted": vs.get("mute", False),
            }

            # Add if not already present (idempotent)
            if not any(u["id"] == user_id for u in self._users):
                self._users.append(user_info)

            # Update backend cache
            self.backend.update_voice_channel_user(
                user_id,
                user_info["username"],
                user_info["nick"],
                user_info["volume"],
                user_info["muted"]
            )

        self._update_display()

    def _on_voice_state_create(self, data: dict):
        """Handle user joining voice channel."""
        if not data:
            return

        user_data = data.get("user", {})
        user_id = user_data.get("id")
        if not user_id:
            return

        # Filter out self
        if user_id == self.backend.current_user_id:
            return

        user_info = {
            "id": user_id,
            "username": user_data.get("username", "Unknown"),
            "nick": data.get("nick"),
            "volume": data.get("volume", 100),
            "muted": data.get("mute", False),
        }

        # Add to local list (avoid duplicates)
        if not any(u["id"] == user_id for u in self._users):
            self._users.append(user_info)

        # Update backend cache
        self.backend.update_voice_channel_user(
            user_id,
            user_info["username"],
            user_info["nick"],
            user_info["volume"],
            user_info["muted"]
        )

        self._update_display()

    def _on_voice_state_delete(self, data: dict):
        """Handle user leaving voice channel."""
        if not data:
            return

        user_data = data.get("user", {})
        user_id = user_data.get("id")
        if not user_id:
            return

        # Remove from local list
        self._users = [u for u in self._users if u["id"] != user_id]

        # Adjust current index if needed
        if self._current_user_index >= len(self._users):
            self._current_user_index = max(0, len(self._users) - 1)

        # Update backend cache
        self.backend.remove_voice_channel_user(user_id)

        self._update_display()

    def _on_voice_state_update(self, data: dict):
        """Handle user voice state change (volume, mute, etc)."""
        if not data:
            return

        user_data = data.get("user", {})
        user_id = user_data.get("id")
        if not user_id:
            return

        # Find and update user
        for user in self._users:
            if user["id"] == user_id:
                if "volume" in data:
                    user["volume"] = data.get("volume")
                if "mute" in data:
                    user["muted"] = data.get("mute")
                if "nick" in data:
                    user["nick"] = data.get("nick")
                break

        self._update_display()

    # === Display ===

    def _update_display(self):
        """Update the dial display with current user info."""
        if not self._in_voice_channel or not self._users:
            self.set_top_label("Not in voice" if not self._in_voice_channel else self._current_channel_name[:12])
            self.set_center_label("")
            self.set_bottom_label("No users" if self._in_voice_channel else "")
            return

        # Truncate channel name for space
        channel_display = self._current_channel_name[:12] if len(self._current_channel_name) > 12 else self._current_channel_name
        self.set_top_label(channel_display)

        if self._current_user_index < len(self._users):
            user = self._users[self._current_user_index]
            display_name = user.get("nick") or user.get("username", "Unknown")
            volume = user.get("volume", 100)

            # Truncate name for display
            display_name = display_name[:10] if len(display_name) > 10 else display_name

            self.set_center_label(display_name)
            self.set_bottom_label(f"{volume}%")
        else:
            self.set_center_label("")
            self.set_bottom_label("No selection")
