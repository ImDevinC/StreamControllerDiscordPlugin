> [!NOTE]
> Only the official Discord application is currently supported. Alternate clients may not work, and
> unfortunately I don't have the capacity to troubleshoot at the moment.

> [!WARNING]
> Vesktop **will not** work with this plugin. This is an issue with Vesktop, and not something I can fix
> in this plugin.

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

## Flatpak
If you are using the Flatpak version of Discord, Discord may not properly setup
the IPC channels. You will need to use the commands below to create the IPC
channel to communicate with Discord.

```bash
mkdir -p ~/.config/user-tmpfiles.d
echo 'L %t/discord-ipc-0 - - - - app/com.discordapp.Discord/discord-ipc-0' > ~/.config/user-tmpfiles.d/discord-rpc.conf
systemctl --user enable --now systemd-tmpfiles-setup.service
```
You will also need to make sure that Discord has access to `/run/user/1000/` to be able to create the IPC file.
Configurable by allowing access to `xdg-run/discord:create`.

If you are using the Flatpak version of StreamController, you will need to make sure StreamController has
access to `/run/user/1000/discord-ipc-*` so it can access the IPC files.

## Troubleshooting
This plugin uses sockets to communicate with Discord. Discord creates this socket as `$XDG_RUNTIME_DIR/discord-ipc-0`.
To verify that only process is listening to this socket, perform the following:
1. Quit Discord, StreamController and any other discord-like applications entirely
1. Run `lsof $XDG_RUNTIME_DIR/discord-ipc-0` and make sure that there are no processes returned
1. Launch Discord and StreamController again, and try to use an action
1. If it doesn't work, check `lsof $XDG_RUNTIME_DIR` again to see how many processes are accessing the socket
