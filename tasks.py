"A collection of regularly scheduled miscellaneus tasks which don't require a separate module."

import calendar
import itertools
import logging
import time
from datetime import datetime, timedelta

import praw
import psycopg2

import dojo
import redesign
import twitch

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


def dojo_leaderboard(subreddit, stream) -> None:
    """
    Performs the workflow of updating the dojo leaderboard. This includes -

    1. ingesting new comments from the Tekken Dojo and adding them to the db
    2. calculating the leaderboard by querying the db
    3. publishing the results to the sidebar widget

    Frequency: 1 day
    """

    logging.debug("Retrieving Tekken Dojo...")
    dojo_post = dojo.get_tekken_dojo(subreddit)
    logging.info("Obtained Tekken Dojo!")
    logging.debug("Ingesting new comments...")
    total_comments = dojo.ingest_new(dojo_post, stream)
    logging.info(f"Successfully ingested {total_comments} new comments!")

    # Find (year, month) to tally scores for
    curr = datetime.now()
    start_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month:02d}-01 00:00:00.000"
    )
    end_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month:02d}-{calendar.monthrange(curr.year, curr.month)[1]} 23:59:59.999"
    )
    logging.debug(
        f"Finding scores for timestamp range [{start_timestamp}, {end_timestamp}]"
    )
    logging.debug(f"Finding scores for {curr.year}-{curr.month:02d}")

    leaders = dojo.tally_scores(start_timestamp, end_timestamp)
    logging.info(f"Found leaders for {curr.year}-{curr.month:02d}")
    dojo.update_dojo_sidebar(subreddit, leaders, curr)
    logging.info(f"Finished dojo leaderboard workflow for {curr.year}-{curr.month:02d}")


def dojo_award(reddit, subreddit) -> None:
    """
    Performs the workflow of publishing the winner and awarding them at the end of each month. This
    includes -
    1. calculating the final leaderboard by querying the db
    2. publishing the leaderboard results to the wiki (each of the top 5 with links to the comments
       included in their score)
    3. awarding custom flairs to the leader

    Frequency: 1st of every month
    """

    # Exit from function if not the 1st of the month
    # Ref.: https://stackoverflow.com/a/57221649
    if datetime.now().day != 1:
        logging.info("Not 1st of the month, skipping award workflow...")
        return

    # Find (year, month) to tally scores for
    curr = datetime.now() - timedelta(hours=24)  # get leaderboard for one day earlier.
    start_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month:02d}-01 00:00:00.000"
    )
    end_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month:02d}-{calendar.monthrange(curr.year, curr.month)[1]} 23:59:59.999"
    )

    comment_urls = dojo.check_db_health(reddit, start_timestamp, end_timestamp)

    logging.debug(f"Finding scores for {curr.year}-{curr.month:02d}")
    curr += timedelta(hours=24)  # to ensure year/month is for the next month
    leaders = dojo.tally_scores(start_timestamp, end_timestamp)

    dojo.award_leader(subreddit, leaders, curr)
    logging.info(f"Finished awarding leaders for {curr.year}-{curr.month:02d}")
    publish_wiki(subreddit, leaders, comment_urls, start_timestamp, end_timestamp)
    logging.info(f"Finished publishing wiki for {curr.year}-{curr.month:02d}")


def dojo_cleaner() -> None:
    """
    Performs the workflow of deleting old comments from the db

    Deletes comments which are older than a certain month threshold. This is necessary to ensure db
    does not exceed capacity limits (10000 rows, 1GB) of hobby-dev tier of Heroku PostGreSQL plan.

    Frequency: 5 months (~ 20 weeks)
    """

    conn = dojo.connect_to_db()
    cur = conn.cursor()

    cutoff = datetime.now() - timedelta(weeks=WEEK_BUFFER)

    logging.debug(f"Deleting comments older than datetime {str(cutoff)}")

    cur.execute(
        sql.SQL(
            """
    DELETE FROM {}
    WHERE created_utc < %s
    """.format(
                sql.Identifier(TABLE_NAME)
            )
        ),
        (cutoff),
    )

    logging.info(f"Deleted {cur.rowcount} rows")

    conn.commit()
    cur.close()
    conn.close()


def update_dojo_links(subreddit) -> None:
    """
    Update all links which reference the Tekken Dojo with the current Tekken Dojo post

    Updates the links in -
    1. menu links (top bar)
    2. sidebar (Useful Stuff - For Beginners)
    3. image widget (Tekken Dojo)
    4. welcome message
    5. old sidebar
    """

    # get current dojo post
    dojo_post = dojo.get_tekken_dojo(subreddit)
    new_permalink = dojo_post.permalink
    new_full_link = "https://www.reddit.com" + new_permalink
    logging.debug(f"Dojo permalink: {new_permalink}")

    # get old link
    curr_welcome_msg_txt = subreddit.mod.settings()["welcome_message_text"]
    m = re.search(
        r"\[\*\*Tekken Dojo\*\*\]\(([^ ]*)\)", curr_welcome_msg_txt, flags=re.MULTILINE
    )
    try:
        old_permalink = m.group(1)
    except:
        logging.debug(f"{curr_welcome_msg_txt}")
        logging.error(traceback.format_exc())
        return
    old_full_link = "https://www.reddit.com" + old_permalink
    logging.debug(f"Old Dojo link: {old_permalink}")

    # Update menu links
    menu = subreddit.widgets.topbar[0]
    data = menu.data
    for i, menu_link in enumerate(menu):
        if menu_link.text == "Tekken Dojo":
            data[i].url = new_full_link
            break
    menu.mod.update(data=data)
    logging.info("Updated top bar menu link")

    # Update sidebar widgets (Useful Stuff TextArea + Tekken Dojo ImageWidget)
    for widget in subreddit.widgets.sidebar:
        if isinstance(widget, praw.models.TextArea):
            if "Useful Stuff" in widget.shortName:
                curr_text = widget.text
                new_text = curr_text.replace(old_full_link, new_full_link)
                logging.debug(f"New sidebar widget text: \n{new_text}")
                widget.mod.update(text=new_text)
                logging.info("Updated Useful Stuff sidebar link")
        elif isinstance(widget, praw.models.ImageWidget):
            if "Tekken Dojo" in widget.shortName:
                img = widget.data
                img[0].linkUrl = new_full_link
                widget.mod.update(data=img)
                logging.info("Updated Tekken Dojo image link")

    # update welcome message
    new_welcome_msg_txt = curr_welcome_msg_txt.replace(old_permalink, new_permalink)
    subreddit.mod.update(welcome_message_text=new_welcome_msg_txt)
    logging.info("Updated welcome message text")

    # update old sidebar
    sidebar = subreddit.wiki["config/sidebar"]
    contents = sidebar.content_md
    new_content = contents.replace(old_full_link, new_full_link)
    new_content = new_content.replace(old_permalink, new_permalink)
    sidebar.edit(new_content)
    logging.info("Updated links in the old sidebar")

    # update stylesheet
    stylesheet = subreddit.stylesheet
    stylesheet_contents = subreddit.stylesheet().stylesheet
    new_stylesheet = stylesheet_contents.replace(old_permalink, new_permalink)
    stylesheet.update(new_stylesheet)
    logging.info("Updated links in the stylesheet")
