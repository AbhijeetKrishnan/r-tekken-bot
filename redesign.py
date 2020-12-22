import logging
import time

import praw

import twitch

MAX_STATUS_LENGTH = 20  # length of status allowed in livestream table
# keep at 20 to prevent a single long string overflowing the available limit
# e.g. 'LMFAOOOOOOoOoOoOoOoOoOoO' takes up the entire table width on my screen
MAX_NUM_STREAMS = 5  # number of streams displayed in livestream table


def get_top_channels(subreddit):
    """
    Returns a Markdown table of the top live streamers for a game
    """

    text = "Twitch | 👁 | Streamer \n"
    text += ":- | :- | :- \n"

    channels = twitch.get_top_channels_raw(subreddit, MAX_NUM_STREAMS)
    logging.info(
        "Streamers: {}".format(", ".join([channel["name"] for channel in channels]))
    )
    if len(channels) == 0:
        return ""

    for channel in channels:
        status = channel["status"]
        if "|" in status:
            status = status[: status.index("|")]
        if len(status) > MAX_STATUS_LENGTH:
            status = status[:MAX_STATUS_LENGTH] + "..."

        text += "[%s](%s) |" % (status, channel["url"])
        text += " %d |" % (channel["viewers"])
        text += " [%s](%s)\n" % (channel["name"], channel["url"])

    text += "***\n"
    text += f"^(Last updated: {time.ctime()} UTC by u/tekken-bot)\n"
    logging.info(f"Livestream widget text -\n{text}")
    return text


# TODO: could refactor this to use widget_shortname and text as parameters
def update_sidebar(subreddit):
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if "Livestreams" in w.shortName:
                text = get_top_channels(subreddit)
                if len(text) > 0:
                    w.mod.update(text=text)
