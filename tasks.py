"A collection of regularly scheduled miscellaneus tasks which don't require a separate module."

import itertools
import logging
from datetime import datetime, timedelta
import time

import praw
import twitch
import redesign
import dojo

SHITPOST_FLAIR_TEXT = "Shit Post"  # text of the shitpost flair
MAX_STATUS_LENGTH = 20  # length of status allowed in livestream table
# keep at 20 to prevent a single long string overflowing the available limit
# e.g. 'LMFAOOOOOOoOoOoOoOoOoOoO' takes up the entire table width on my screen
MAX_NUM_STREAMS = 5  # number of streams displayed in livestream table


def get_removal_reason(subreddit):
    for removal_reason in subreddit.mod.removal_reasons:
        if removal_reason.title == "Off-schedule shitpost":
            return removal_reason


def delete_shitposts(subreddit, stream, flair_text=SHITPOST_FLAIR_TEXT, day=5):
    """
    Deletes all posts not posted on the scheduled day whose flair text is 'flair_text'.

    Parameters:
        subreddit - the subreddit to make changes in
        day - the day of the week [1, 7] designated for posts with the given flair text
    """
    if day not in range(1, 8):
        logging.warning(f"Invalid day of week ({day}). Setting day to Fri (5) instead.")
        day = 5
    logging.debug(f"Deleting posts with flair: {flair_text}")
    while submission := next(stream):
        logging.debug(submission.title)
        if submission.link_flair_text == flair_text:
            logging.debug(f"Submission flair matches {flair_text}!")
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
                    logging.debug(f"Lies on {day} with delta {delta}")
                    lies_on_day = True
                    break
            if not lies_on_day:
                # delete post
                logging.info(
                    f"Deleting post: https://www.reddit.com{submission.permalink}"
                )
                logging.debug("Getting removal reason for shitpost deletion")
                removal_reason = get_removal_reason(subreddit)
                logging.debug(
                    f"Removing post with removal reason id {removal_reason.id}"
                )
                submission.mod.remove(reason_id=removal_reason.id)
                logging.debug(f"Sending removal message {removal_reason.message}")
                submission.mod.send_removal_message(
                    removal_reason.message, type="public"
                )
            else:
                logging.debug(f"Does not lie on {day}, no action")


def update_livestream_widget(subreddit) -> None:
    """
    Update the livestream widget in the redesign and on old Reddit
    """

    text = twitch.get_top_channels(subreddit, MAX_NUM_STREAMS, MAX_STATUS_LENGTH)
    redesign.update_sidebar_widget(
        subreddit,
        "Livestreams",
        text,
    )
    redesign.update_sidebar_old(subreddit, "Livestreams", text)


def update_events(subreddit) -> None:
    """
    Update the Upcoming Events section of the sidebar on old Reddit
    """

    # get Calendar widget
    for widget in subreddit.widgets.sidebar:
        if widget.shortName == "Upcoming Events":
            calendar = widget
            logging.debug("Found Upcoming Events Calendar widget!")
    text = "Name | Starts (UTC) | Location\n"
    text += ":-- | :-: | :--\n"
    for event in calendar.data:
        title = event["title"]
        dt = datetime.fromtimestamp(event["startTime"])
        location = event["location"]
        text += f"{title} | {dt.strftime('%a %b %e %I:%M %p')} | {location}\n"
        logging.debug(f"Adding event {title} {dt} {location}")
    text += "***\n"
    text += f"^(Last updated: {time.ctime()} UTC by u/tekken-bot)\n"
    redesign.update_sidebar_old(subreddit, "Upcoming Events", text)
