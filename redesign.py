import logging
import time

import praw


def update_sidebar_widget(subreddit, short_name: str, text: str) -> None:
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if short_name in w.shortName:
                if len(text) > 0:
                    w.mod.update(text=text)
