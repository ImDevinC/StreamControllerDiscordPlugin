from discordrpc import Discord
import os

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")

if __name__ == '__main__':
    dc = Discord(client_id, client_secret)
    dc.connect()
    dc.authenticate(access_token)
    vs = dc.get_voice_settings()
    print(vs)
    settings = {"mute": False}
    dc.set_voice_settings(settings)
    vs = dc.get_voice_settings()
    print(vs)
    dc.disconnect()
