import configparser
import os
import traceback
from datetime import datetime

import requests

clientID = os.environ.get("TWITCH_CLIENT_ID")
clientSecret = os.environ.get("TWITCH_SECRET_ID")

config = configparser.ConfigParser()
if config.read('config.txt'):
    clientID = config['twitch.com']['TWITCH_CLIENT_ID']
    clientSecret = config['twitch.com']['TWITCH_SECRET_ID']

def _get_top_channels_raw(game_id: str, maxLength: int=5):
    "Get top channels based on game_id"

    oauthURL = 'https://id.twitch.tv/oauth2/token'
    data = {'client_id': clientID, 'client_secret': clientSecret, 'grant_type': 'client_credentials'}
    try:
        r = requests.post(oauthURL, data=data)
    except requests.exceptions.HTTPError as err:
        traceback.print_exc()
        raise SystemExit(err)
    if r.status_code != requests.codes.ok:
        print('Received bad request with code', r.status_code)
        raise SystemExit
    access_token = r.json()['access_token']

    headers = {'Client-ID': clientID, 'Authorization': 'Bearer ' + access_token}

    top_channels = []

    # Getting top channels based on url
    stream_api_url = f"https://api.twitch.tv/helix/streams?game_id={game_id}&first={maxLength}"
    print(stream_api_url)
    try:
        r = requests.get(stream_api_url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    channels = r.json()
    print(channels)

    if "data" not in channels:
        return top_channels
    else:
        channels = channels["data"]
    
    # Getting user_ids based on channels
    # Need to make additional request to user endpoint since user_name is not display name
    # Reference: https://github.com/twitchdev/issues/issues/3
    user_ids = [stream["user_id"] for stream in channels]
    print(user_ids)
    user_api_url = f"https://api.twitch.tv/helix/users?id={'&id='.join(user_ids)}"
    print(user_api_url)
    try:
        r = requests.get(user_api_url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    users = r.json()

    if "data" not in users:
        return top_channels
    else:
        users = users["data"]

    for stream, user in zip(channels, users):
        viewers = stream["viewer_count"]
        status = stream["title"]
        name = stream["user_name"]
        user_id = stream["user_id"]
        login_name = user["login"]
        streamer_url = "https://www.twitch.tv/" + login_name

        # Correcting status for display in Markdown
        if '`' in status:
            status = status.replace("`", "\`")
        if '[' in status:
            status = status.replace("[", "\[")
        if ']' in status:
            status = status.replace("]", "\]")
        if '\r' in status:
            status = status.replace("\r", '')
        if '\n' in status:
            status = status.replace("\n", '')
        if '_' in name:
            name = name.replace('_', '\_')

        sidebar_channel = {
            "name": name, 
            "status": status,
            "viewers": viewers, 
            "url": streamer_url
        }
        print(sidebar_channel)
        top_channels.append(sidebar_channel)

    return top_channels

def get_top_channels_raw(sub, maxLength=5):
    "Returns list of channels based on subreddit."
    
    try:
        if config:
            game_id = config['game-ids']['tekken']
        else:
            game_id = os.environ.get(sub.display_name.lower())
        return _get_top_channels_raw(game_id, maxLength)
    except Exception:
        return []
