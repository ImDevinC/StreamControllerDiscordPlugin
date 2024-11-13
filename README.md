## Expected flow
1. Create a Discord app at https://discord.com/developers/applications
1. Get a client ID and Client Secret
1. Make sure to set a `redirect url` of `http://localhost:9000` in the Oauth2 settings page
1. Use the Client ID and Client Secret on any of the actions (applying to one action will apply to all)

## Currently supported features
Currently, this plugin supports the following:

- Mute/Unmute
- Deafen/Undeafen
- Join/Leave voice channel
- Join text channel

# Flatpak
If you are using the Flatpak version of Discord, Discord may not properly setup
the IPC channels. You will need to use the commands below to create the IPC
channel to communicate with Discord.

```bash
mkdir -p ~/.config/user-tmpfiles.d
echo 'L %t/discord-ipc-0 - - - - app/com.discordapp.Discord/discord-ipc-0' > ~/.config/user-tmpfiles.d/discord-rpc.conf
systemctl --user enable --now systemd-tmpfiles-setup.service
```
You will also need to make sure that Discord has access to `/run/user/1000/` to be able to create the IPC file.

If you are using the Flatpak version of StreamController, you will need to make sure StreamController has
access to `/run/user/1000/discord-ipc-*` so it can access the IPC files.
