import praw

import twitch

MAX_STATUS_LENGTH = 30 # length of status allowed in livestream table
MAX_NUM_STREAMS = 5    # number of streams displayed in livestream table

def get_top_channels(sub):
    text = "Twitch | 👁 | Streamer \n"
    text += ":- | :- | :- \n"

    channels = twitch.get_top_channels_raw(sub, MAX_NUM_STREAMS)
    print('Streamers: ', ', '.join([channel["name"] for channel in channels]))
    if len(channels) == 0:
        return ""

    for channel in channels:
        status = channel["status"]
        if "|" in status:
            status = status[:status.index("|")]
        if len(status) > MAX_STATUS_LENGTH:
            status = status[:MAX_STATUS_LENGTH] + "..."

        text += "[%s](%s) |" % (status, channel["url"])
        text += " %d | " % (channel["viewers"])
        text += "[%s](%s) \n " % (channel["name"], channel["url"])
    return text

def update_sidebar(sub):
    for w in sub.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if "Livestreams" in w.shortName:
                text = get_top_channels(sub)
                if len(text) > 0:
                    w.mod.update(text=text)
