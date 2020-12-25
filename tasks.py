"A collection of regularly scheduled miscellaneus tasks which don't require a separate module."

import itertools
import logging
from datetime import datetime, timedelta

import praw

SHITPOST_FLAIR_TEXT = "Shit Post"  # text of the shitpost flair


def get_removal_reason_id(subreddit):
    for removal_reason in subreddit.mod.removal_reasons:
        if removal_reason.title == "Off-schedule shitpost":
            return removal_reason.id


def delete_shitposts(stream, flair_text=SHITPOST_FLAIR_TEXT, day=6):
    """
    Deletes all posts not posted on the scheduled day whose flair text is 'flair_text'.

    Parameters:
        subreddit - the subreddit to make changes in
        day - the day of the week [1, 7] designated for posts with the given flair text
    """
    if day not in range(1, 8):
        logging.warning(f"Invalid day of week ({day}). Setting day to Sat (6) instead.")
        day = 7
    while submission := next(stream):
        if submission.link_flair_text == flair_text:
            logging.debug(submission.title)
            # Check timestamp if it is lies on the given day for all timezones in [-12:00, +14:00]
            timestamp = datetime.fromtimestamp(int(submission.created_utc))
            lies_on_day = False
            for hours, mins in (
                [(-12, 0)]
                + list(itertools.product(range(-11, 14), (0, 30)))
                + [(14, 0)]
            ):
                delta = timedelta(hours=hours, minutes=mins)
                new_dt = timestamp + delta
                if new_dt.isoweekday() == day:
                    lies_on_day = True
            if not lies_on_day:
                # delete post
                logging.info(
                    f"Deleting post: https://www.reddit.com{submission.permalink}"
                )
                # submission.mod.remove(reason_id=get_removal_reason_id(subreddit))
