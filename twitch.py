import logging
import os
import traceback
from datetime import datetime
from typing import List, Dict, cast
import time

import requests

clientID = os.environ.get("TWITCH_CLIENT_ID")
clientSecret = os.environ.get("TWITCH_SECRET_ID")


def _get_top_channels_raw(game_id: str, maxLength: int = 5) -> List[Dict[str, str]]:
    "Get top channels based on game_id"

    oauthURL = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": clientID,
        "client_secret": clientSecret,
        "grant_type": "client_credentials",
    }
    try:
        r = requests.post(oauthURL, data=data)
    except requests.exceptions.HTTPError as err:
        logging.error(traceback.format_exc())
        raise SystemExit(err)
    if r.status_code != requests.codes.ok:
        logging.error("Received bad request with code", r.status_code)
        raise SystemExit
    access_token = r.json()["access_token"]

    headers = {"Client-ID": clientID, "Authorization": "Bearer " + access_token}

    top_channels: List[Dict[str, str]] = []

    # Getting top channels based on url
    stream_api_url = (
        f"https://api.twitch.tv/helix/streams?game_id={game_id}&first={maxLength}"
    )
    logging.debug(stream_api_url)
    try:
        r = requests.get(stream_api_url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    channels = r.json()
    logging.debug(channels)

    if "data" not in channels:
        return top_channels
    else:
        channels = channels["data"]

    # Getting user_ids based on channels
    # Need to make additional request to user endpoint since user_name is not display name
    # Reference: https://github.com/twitchdev/issues/issues/3
    user_ids = [stream["user_id"] for stream in channels]
    logging.debug(user_ids)
    user_api_url = f"https://api.twitch.tv/helix/users?id={'&id='.join(user_ids)}"
    logging.debug(user_api_url)
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
        if "`" in status:
            status = status.replace("`", "\`")
        if "[" in status:
            status = status.replace("[", "\[")
        if "]" in status:
            status = status.replace("]", "\]")
        if "\r" in status:
            status = status.replace("\r", "")
        if "\n" in status:
            status = status.replace("\n", "")
        if "_" in name:
            name = name.replace("_", "\_")

        sidebar_channel = {
            "name": name,
            "status": status,
            "viewers": viewers,
            "url": streamer_url,
        }
        logging.debug(sidebar_channel)
        top_channels.append(sidebar_channel)

    return top_channels


def get_top_channels_raw(sub, maxLength: int = 5) -> List[Dict[str, str]]:
    "Returns list of channels based on subreddit."

    try:
        game_id: str = cast(str, os.environ.get(sub.display_name.lower()))
        if not game_id:
            logging.error(f"No game_id provided: '{game_id}'")
            raise Exception
        return _get_top_channels_raw(game_id, maxLength)
    except Exception:
        return []


def get_top_channels(subreddit, num_streams=5, status_length=20) -> str:
    """
    Returns a Markdown table of the top live streamers for a game
    """

    text = "Twitch | 👁 | Streamer \n"
    text += ":- | :- | :- \n"

    channels = get_top_channels_raw(subreddit, num_streams)
    logging.info(
        "Streamers: {}".format(", ".join([channel["name"] for channel in channels]))
    )
    if len(channels) == 0:
        return ""

    for channel in channels:
        status = channel["status"]
        if "|" in status:
            status = status[: status.index("|")]
        if len(status) > status_length:
            status = status[:status_length] + "..."

        text += "[%s](%s) |" % (status, channel["url"])
        text += " %d |" % (channel["viewers"])
        text += " [%s](%s)\n" % (channel["name"], channel["url"])

    text += "***\n"
    text += f"^(Last updated: {time.ctime()} UTC by u/tekken-bot)\n"
    logging.info(f"Livestream widget text -\n{text}")
    return text
