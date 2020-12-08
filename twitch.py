import configparser
import os
from datetime import datetime

import requests

config = configparser.ConfigParser()
config.read("config.txt")

clientID = config["twitch.com"]["TWITCH_CLIENT_ID"]
clientSecret = config["twitch.com"]["TWITCH_SECRET_ID"]

def filter_channel(stream) -> bool:
    "Check if a stream should be skipped for any reason."

    title = stream['title'].lower()
    if 'arcana' in title or 'free' in title:
        return True

    channel = stream["user_name"].lower()
    impersonated = [
        'arteezy',
        'zai',
        'admiralbulldog',
        'eternalenvyy',
        'sumayyl',
        'gorgc',
        'wagamamatv',
        'topsonous',
        'miracle_doto',
        'bigdaddy',
    ]
    return any((channel.startswith(username) or username in title)
               and channel != username for username in impersonated)

def _get_top_channels_raw(url, maxLength=None):
    "Get top channels based on URL"

    oauthURL = 'https://id.twitch.tv/oauth2/token'
    data = {'client_id': clientID, 'client_secret': clientSecret, 'grant_type': 'client_credentials'}
    r = requests.post(oauthURL, data=data)

    access_token = r.json()['access_token']


    headers = {'Client-ID': clientID, 'Authorization': 'Bearer ' + access_token}

    r = requests.get(url, headers=headers)

    channels = r.json()
    top_channels = []

    if 'data' not in channels:
        return top_channels

    for stream in channels['data']:
        if maxLength and len(top_channels) >= maxLength:
            break

        # if filter_channel(stream):
        #     continue

        viewers = stream["viewer_count"]
        status = stream["title"]
        name = stream["user_name"]
        url = "https://www.twitch.tv/" + name

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

        sidebar_channels = {"name": name, "status": status,
                            "viewers": viewers, "url": url}
        top_channels.append(sidebar_channels)

    return top_channels

def get_top_channels_raw(sub, maxLength=None):
    "Returns list of channels based on subreddit."
    
    try:
        return _get_top_channels_raw(config['game-urls'][sub.display_name.lower()], maxLength)
    except Exception:
        return []
