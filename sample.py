from discordrpc import AsyncDiscord
import os
import time
from discordrpc import commands
import json

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")

client = AsyncDiscord(client_id, client_secret)

auth_code = ""


def callback(value):
    # code = value[0]
    payload = json.loads(value[1])
    match payload:
        case "AUTHORIZE":
            global auth_code
            print('setting auth code')
            auth_code = payload.get('data').get('code')
        case "AUTHENTICATE":
            pass
    print(f"callback: {payload}")


if __name__ == '__main__':
    client.connect(callback)
    client.authorize()
    while auth_code == "":
        print('waiting for auth_code')
        time.sleep(1)
        continue
    access_token = client.get_access_token(auth_code)
    while access_token == "":
        print('waiting for access token')
        time.sleep(1)
        continue
    client.authenticate(access_token)
    time.sleep(1)
    client.subscribe('VOICE_SETTINGS_UPDATE')
    time.sleep(2)
    client.set_voice_settings({'mute': True})
    time.sleep(2)
    client.set_voice_settings({'mute': False})
    time.sleep(5)
    # dc = Discord(client_id, client_secret)
    # dc.access_token = access_token
    # dc.connect()
    # dc.authenticate()
    # dc.start_polling(callback)
    # dc.subscribe("VOICE_SETTINGS_UPDATE")
    # vs = dc.get_voice_settings()
    # print(vs)
    # settings = {"mute": True}
    # dc.set_voice_settings(settings)
    # time.sleep(2)
    # settings = {"mute": False}
    # dc.set_voice_settings(settings)
    # vs = dc.get_voice_settings()
    # print(vs)
    # time.sleep(5)
    # dc.disconnect()
