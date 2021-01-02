import datetime
import logging
import os
import time

import praw
import schedule

import dojo
import redesign
import tasks
import twitch

r = None

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s:%(message)s", level=logging.INFO
)


def login() -> int:
    global r

    r = praw.Reddit(
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        password=os.environ["PASSWORD"],
        user_agent="u/tekken-bot by u/pisciatore",
        username=os.environ["BOT_USERNAME"],
    )
    try:
        logging.debug(r.user.me())
        logging.info("Login successful!")
        return 0
    except Exception:
        logging.error("Login unsuccessful")
        return 1


if __name__ == "__main__":
    logging.debug("Attempting to login...")
    if login():
        logging.error("Exiting application...")
        exit(1)

    tekken = r.subreddit("Tekken")
    tekken_comment_stream = tekken.stream.comments(skip_existing=True, pause_after=0)
    tekken_submission_stream = tekken.stream.submissions(
        skip_existing=True, pause_after=0
    )

    logging.info("Starting tasks...")

    schedule.every(30).seconds.do(tasks.update_livestream_widget, subreddit=tekken)
    schedule.every(30).seconds.do(
        tasks.delete_shitposts, stream=tekken_submission_stream, day=5
    )
    schedule.every(60).seconds.do(
        dojo.dojo_leaderboard, subreddit=tekken, stream=tekken_comment_stream
    )
    schedule.every(1).day.at("00:00:00").do(dojo.dojo_award, reddit=r, subreddit=tekken)
    schedule.every(20).weeks.do(dojo.dojo_cleaner)
    schedule.every(4).weeks.do(dojo.update_dojo_links, subreddit=tekken)

    while True:
        schedule.run_pending()
        time.sleep(1)
