# WIP
This is still a work in progress and not fully functional. Use at your own risk.

See `sample.py` for an example of how this works (generating an access token is still not part of the flow, but can be done manually)

## Expected flow
1. Create a Discord app at https://discord.com/developers/applications
1. Get a client ID and Client Secret
1. Create a new Discord client `client = discordrpc.Discord(client_id, client_secret)`
1. Call `client.connect()`
1. Call `client.authenticate()`
1. Client can now be used
1. Be sure to call `client.disconnect()` before closing

## Currently supported features
Full list here: https://discord.com/developers/docs/topics/rpc
- GetVoiceSettings: Returns the current voice settings for the logged in user
- SetVoiceSettings: Allows setting voice settings
