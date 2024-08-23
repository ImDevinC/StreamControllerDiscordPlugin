# WIP
This is still a work in progress and not fully functional. Use at your own risk.

## Expected flow
1. Create a Discord app at https://discord.com/developers/applications
1. Get a client ID and Client Secret
1. When you add an action, add those values in
> [!NOTE]
> For now, you will most likely need to restart StreamController after authenticating.
> I will work on this in the future

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

If you are using the Flatpak version of StreamController, you will need to make sure StreamController has
access to `/run/user/1000/discord-ipc-*` so it can access the IPC files.
> [!NOTE]
> There is probably a better way to do this, will investigate later
