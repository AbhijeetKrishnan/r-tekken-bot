import logging

import praw

import twitch

MAX_STATUS_LENGTH = 30 # length of status allowed in livestream table
MAX_NUM_STREAMS = 5    # number of streams displayed in livestream table

def get_top_channels(subreddit):
    text = "Twitch | 👁 | Streamer \n"
    text += ":- | :- | :- \n"

    channels = twitch.get_top_channels_raw(subreddit, MAX_NUM_STREAMS)
    logging.info('Streamers: {}'.format(', '.join([channel["name"] for channel in channels])))
    if len(channels) == 0:
        return ""

    for channel in channels:
        status = channel["status"]
        if "|" in status:
            status = status[:status.index("|")]
        if len(status) > MAX_STATUS_LENGTH:
            status = status[:MAX_STATUS_LENGTH] + "..."

        text += "[%s](%s)|" % (status, channel["url"])
        text += "%d|" % (channel["viewers"])
        text += "[%s](%s)\n" % (channel["name"], channel["url"])
    
    text += "***\n^(This widget is auto-updated by u/tekken-bot developed by u/pisciatore.)" # credit myself
    logging.info(f'Livestream widget text -\n{text}')
    return text

def update_sidebar(subreddit):
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if 'Livestreams' in w.shortName:
                text = get_top_channels(subreddit)
                if len(text) > 0:
                    w.mod.update(text=text)
