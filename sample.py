from discordrpc import AsyncDiscord
import os
import time
from discordrpc import commands
import json

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
access_token = os.getenv("ACCESS_TOKEN")

client = AsyncDiscord(client_id, client_secret)

AUTH_CODE = ""


def callback(value):
    code = value[0]
    print(f"code {code}")
    if code == 0:
        return
    try:
        payload = json.loads(value[1])
    except:
        print(f"failed to parse payload: {value[1]}")
        return
    match payload['cmd']:
        case "AUTHORIZE":
            print('setting auth code')
            global AUTH_CODE
            AUTH_CODE = payload.get('data').get('code')
        case "AUTHENTICATE":
            pass
        case _:
            print(f"callback: {payload}")


if __name__ == '__main__':
    try:
        client.connect(callback)
#        client.authorize()
#        while AUTH_CODE == "":
#            print('waiting for auth_code')
#            time.sleep(1)
#            continue
#        access_token = client.get_access_token(AUTH_CODE)
#        while access_token == "":
#            print('waiting for access token')
#            time.sleep(1)
#            continue
#        print(f"access token: {access_token}")
        client.authenticate(access_token)
        time.sleep(1)
        client.subscribe('VOICE_SETTINGS_UPDATE')
        client.subscribe('VOICE_CHANNEL_SELECT')
        time.sleep(2)
        client.select_voice_channel("752194529288781845", True)
        time.sleep(5)
        client.select_voice_channel(None)
        time.sleep(2)
        client.select_text_channel("814554714283704350")
        # client.set_voice_settings({'mute': True})
        # time.sleep(2)
        # client.set_voice_settings({'mute': False})
        # time.sleep(5)

    except Exception as ex:
        print(ex)
        pass
    client.disconnect()
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
