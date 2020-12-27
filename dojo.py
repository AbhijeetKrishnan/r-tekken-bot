"Implements tasks required for the Dojo system on r/Tekken."

import calendar
import logging
import os
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import re

import praw
import psycopg2
import schedule
from psycopg2 import sql

import redesign

TABLE_NAME: str = (
    "dojo_comments"  # the name of the table where Tekken Dojo comments are stored
)
LEADERBOARD_SIZE: int = 5  # the top-k commenters will be displayed
WEEK_BUFFER: int = 20  # delete comments from the database older than these many weeks
DOJO_MASTER_FLAIR_ID: str = "cc570168-4176-11eb-abb3-0e92e4d477f5"


def connect_to_db():
    "Connect to database and return the connection object."

    DATABASE_URL = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn


def get_tekken_dojo(subreddit):
    """
    The Tekken Dojo is assumed to be the first pinned post of the subreddit.

    Returns: the Submission object of the Tekken Dojo post
    """

    tekken_dojo = subreddit.sticky()
    return tekken_dojo


def is_unhelpful(comment) -> bool:
    """
    Returns True if a comment should not be counted towards a user's total Dojo Points

    A comment which is not providing helpful information to a question (top-level comment) on the
    Tekken Dojo should not be counted towards a user's total. Spam/low-effort comments will
    hopefully be reported and deleted so that when awards are computed, the check_db_health function
    will remove them from the db. Comments like 'No problem!' or "You're welcome" are not
    spam/low-effort but should still not be counted. This function checks for these sort of comments
    """

    is_unhelpful = False
    if not comment:
        logging.error("Comment object was None")
        return False
    if not comment.body:
        logging.warning(f"Comment {comment.id} was deleted")
        return False
    filter = [
        "you're welcome",
        "no problem",
    ]
    for text in filter:
        if text.lower() in comment.body.lower():
            is_unhelpful = True

    return is_unhelpful


def ingest_new(submission, stream) -> int:
    """
    Ingest all new comments made on the submmission into the database.
    Assumes table TABLE_NAME is already created
    """

    logging.debug("Connecting to db...")
    conn = connect_to_db()
    logging.debug("Connected to db!")
    cur = conn.cursor()

    records = 0  # to count total number of comments inserted into the db

    new_comments = []
    try:
        while comment := next(stream):
            logging.debug(f"Found comment {comment.id} in stream")
            if comment.submission == submission:
                new_comments.append(comment)
                logging.debug(
                    f"Comment {comment.id} belongs to submission {submission.id}!"
                )
    except:
        logging.error(traceback.format_exc())

    for (
        comment
    ) in (
        new_comments
    ):  # ref.: https://praw.readthedocs.io/en/latest/tutorials/comments.html

        # Find root comment of this comment
        ancestor = comment
        while not ancestor.is_root:
            ancestor = ancestor.parent()
        if ancestor.author == comment.author:
            continue

        # Account for comment being deleted, which means comment.author is None
        if comment.author:
            author = comment.author.name
        else:
            author = "[deleted]"

        # TODO: Filter comment if its content is not helpful
        if is_unhelpful(comment):
            continue

        record = (comment.id, datetime.fromtimestamp(comment.created_utc), author)
        logging.debug("Comment record: ({}, {}, {})".format(*record))
        try:
            cur.execute(
                sql.SQL(
                    """
            INSERT INTO {} (id, created_utc, author) 
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """
                ).format(sql.Identifier(TABLE_NAME)),
                record,
            )
            if cur.rowcount == 0:
                logging.debug("Comment already exists in db!")
            else:
                logging.debug("Inserted comment into db")
            records += cur.rowcount
        except:
            logging.error(traceback.format_exc())
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    logging.debug("Closing connection...")
    conn.close()
    return records


def tally_scores(
    start_timestamp: datetime, end_timestamp: datetime
) -> List[Tuple[int, str, int]]:
    """
    Go through database to produce count of final scores + comment_ids for comments lying in range
    [start_timestamp, end_timestamp]
    """

    logging.debug("Connecting to db...")
    conn = connect_to_db()
    logging.debug("Connected to db!")
    cur = conn.cursor()

    query = sql.SQL(
        """
    WITH monthly_leaderboard AS (
        SELECT author, COUNT(*) AS c
        FROM {}
        WHERE 
        created_utc BETWEEN %s AND %s
        AND
        author != '[deleted]'
        GROUP BY author
        ORDER BY COUNT(*) DESC
        LIMIT %s
    ),
    last_count AS (
        SELECT monthly_leaderboard.c AS c
        FROM monthly_leaderboard
        OFFSET %s
    ),
    trailers AS (
        SELECT author, COUNT(*) AS c
        FROM {}
        WHERE created_utc BETWEEN %s AND %s
        GROUP BY author
        HAVING COUNT(*) = (SELECT last_count.c FROM last_count)
    )
    SELECT * FROM monthly_leaderboard
    UNION
    SELECT * FROM trailers
    ORDER BY c DESC
    """
    ).format(sql.Identifier(TABLE_NAME), sql.Identifier(TABLE_NAME))
    params = (
        start_timestamp,
        end_timestamp,
        LEADERBOARD_SIZE,
        LEADERBOARD_SIZE - 1,
        start_timestamp,
        end_timestamp,
    )

    logging.debug(
        cur.mogrify(
            query,
            params,
        )
    )
    cur.execute(
        query,
        params,
    )

    leaders: List[
        Tuple[int, str, int]
    ] = []  # stores (rank, username, score) for each user in leaderboard
    last_score: int = -1
    rank: int = 0
    while record := cur.fetchone():
        curr_score = record[1]
        if last_score != curr_score:
            rank += 1
            last_score = curr_score
        leader_record = (rank, record[0], record[1])
        logging.debug(f"Obtained leaderboard entry {leader_record}")
        leaders.append(leader_record)

    cur.close()
    logging.debug("Closing connection...")
    conn.close()
    logging.info(f"Leaderboard for {start_timestamp.month}: {leaders}")
    return leaders


def check_db_health(reddit, start_timestamp, end_timestamp) -> Dict[str, str]:
    """
    Ensures that every comment in the database in the range [start_timestamp, end_timestamp] still
    exists i.e. has not been deleted.

    Goes through every comment in the database in the given range and checks if the comment body is
    present. If not, it is deleted.
    """

    logging.debug("Connecting to db...")
    conn = connect_to_db()
    logging.debug("Connected to db!")
    cur = conn.cursor()
    cur.execute(
        sql.SQL(
            """
    SELECT id from {}
    WHERE created_utc BETWEEN %s AND %s
    """
        ).format(sql.Identifier(TABLE_NAME)),
        (start_timestamp, end_timestamp),
    )

    url_list: Dict[str, str] = {}
    while record := cur.fetchone():
        logging.debug(f"Fetched record {record}")
        comment = reddit.comment(record[0])
        if not comment.body:
            cur.execute(
                sql.SQL(
                    """
            DELETE FROM {}
            WHERE id = %s
            """
                ).format(sql.Identifier(TABLE_NAME)),
                (comment.id),
            )
            logging.info(f"Deleted record for comment {comment.id} from db")
        else:
            url_list[comment.id] = comment.permalink
    return url_list


def get_leaderboard_text(leaders) -> str:
    """
    Generate the Markdown text to display in the Dojo Leaderboard TextArea widget. Only visible in
    the redesign.
    """

    text = "Rank | User | Points \n"
    text += ":-: | :- | :-: \n"
    for rank, user, points in leaders:
        text += f"{rank} | u/{user} | {points}\n"
    text += "***\n"
    text += f"^(Last updated: {time.ctime()} UTC by u/tekken-bot)\n"
    logging.info(f"Leaderboard widget text - \n{text}")
    return text


def update_dojo_sidebar(subreddit, leaders, dt) -> None:
    """
    Update the Dojo Leaderboard TextArea widget with the current leaderboard contents. Also use the
    current datetime to update the widget title.
    """
    # TODO: refactor this so that it can be handled by redesign.update_sidebar funcs itself
    year = "'" + str(dt.year)[-2:]
    month = calendar.month_name[dt.month][:3]
    text = get_leaderboard_text(leaders)
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if "Dojo Leaderboard" in w.shortName:
                new_short_name = f"Dojo Leaderboard ({month} {year})"
                if len(text) > 0:
                    logging.info(
                        f"Updating Dojo Leaderboard widget shortName as {new_short_name}"
                    )
                    w.mod.update(shortName=new_short_name, text=text)

    redesign.update_sidebar_old(
        subreddit, "Dojo Leaderboard", text, f"Dojo Leaderboard ({month} {year})"
    )


def award_leader(subreddit, leaders, dt) -> None:
    """
    Awards user(s) with Dojo Master flair and removes flair from previous Dojo Master.

    Flair is appended to end of users' existing flair with '| Dojo Master (Mon)'.
    Previous Dojo Masters' Flair is changed to Mokujin with their original flair text restored.
    """

    # Generate flair text to be appended to leader flair
    year = f"'{str(dt.year)[2:]}"
    month = calendar.month_name[dt.month][:3]
    dojo_flair_text = f"Dojo Master ({month} {year})"
    logging.debug(f"Dojo flair text generated is {dojo_flair_text}")

    # Remove dojo flair from previous leader
    for flair in subreddit.flair(limit=None):
        if flair["flair_css_class"] == "dojo-master":
            logging.info(
                f'Setting flair of previous leader {flair["user"].name} to {flair["flair_text"].rsplit("|")[0]}'
            )
            subreddit.flair.set(
                flair["user"].name,
                text=flair["flair_text"].rsplit("|")[0],
                css_class="mokujin",
            )

    # Set flair of leader(s)
    for rank, user, points in leaders:
        if rank == 1:
            original_flair_text = next(subreddit.flair(user))["flair_text"].rstrip()
            logging.debug(
                f"Original flair text obtained for {user} is '{original_flair_text}'"
            )
            new_flair_text = f"{original_flair_text} | {dojo_flair_text}"
            subreddit.flair.set(
                user, text=new_flair_text, flair_template_id=DOJO_MASTER_FLAIR_ID
            )
            logging.info(f"Set flair of {user} as '{new_flair_text}'")


def publish_wiki(subreddit, leaders, comment_urls, start_dt, end_dt) -> None:
    """
    Publishes the results of the leaderboard for the month's wiki.

    Each (year, month) has a separate page for it, where each page is a table listing the top 5 dojo
    point winners, along with a list of links to the comments which earned them those points.
    """

    # Write header
    year = f"'{str(start_dt.year)[2:]}"
    month = calendar.month_name[start_dt.month][:3]
    text = f"# Leaderboard for ({month} {year})\n\n"

    # For each author, get comments made by them in the given timeframe
    logging.debug("Connecting to db...")
    conn = connect_to_db()
    logging.debug("Connected to db!")
    cur = conn.cursor()
    url_list = []
    for _, author, score in leaders:
        curr_url_list = []
        cur.execute(
            sql.SQL(
                """
        SELECT id from {}
        WHERE author = %s
        AND
        created_utc BETWEEN %s AND %s
        """
            ).format(sql.Identifier(TABLE_NAME)),
            (author, start_dt, end_dt),
        )
        if cur.rowcount != score:
            logging.error(
                f"# of rows retrieved for {author} does not match their score ({score})!"
            )
        while record := cur.fetchone():
            logging.debug(f"Retrieved record {record}")
            permalink = comment_urls[record[0]]
            curr_url_list.append(permalink)
        url_list.append(curr_url_list)

    # Create table
    table = "Rank | User | Score | Comments\n"
    table += ":-: | :-: | :-: | :--\n"
    for (rank, author, score), author_url_list in zip(leaders, url_list):
        url_str = ", ".join(
            f"[{idx + 1}]({url})" for idx, url in enumerate(author_url_list)
        )
        row = f"{rank} | u/{author} | {score} | {url_str}\n"
        table += row
    text += table

    # Add update UTC
    text += f"^(Created by u/tekken-bot on {time.ctime()})\n"
    text += "***\n"

    logging.info(f"Wiki text generated for ({month} {year}) is - \n{text}")

    # Update wiki
    try:
        dojo_leaderboard_wiki = subreddit.wiki["tekken-dojo/dojo-leaderboard"]
        existing_text = dojo_leaderboard_wiki.content_md
        new_text = text + existing_text
        dojo_leaderboard_wiki.edit(
            content=new_text, reason=f"Update for {month} {year}"
        )
    except:
        logging.error(traceback.format_exc())


def dojo_leaderboard(subreddit, stream) -> None:
    """
    Performs the workflow of updating the dojo leaderboard. This includes -

    1. ingesting new comments from the Tekken Dojo and adding them to the db
    2. calculating the leaderboard by querying the db
    3. publishing the results to the sidebar widget

    Frequency: 1 day
    """

    logging.info("Retrieving Tekken Dojo...")
    dojo = get_tekken_dojo(subreddit)
    logging.info("Obtained Tekken Dojo!")
    logging.info("Ingesting new comments...")
    total_comments = ingest_new(dojo, stream)
    logging.info(f"Successfully ingested {total_comments} new comments!")

    # Find (year, month) to tally scores for
    curr = datetime.now()
    start_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month}-01 00:00:00.000"
    )
    end_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month}-{calendar.monthrange(curr.year, curr.month)[1]} 23:59:59.999"
    )
    logging.debug(
        f"Finding scores for timestamp range [{start_timestamp}, {end_timestamp}]"
    )
    logging.info(f"Finding scores for {curr.year}-{curr.month}")

    leaders = tally_scores(start_timestamp, end_timestamp)
    update_dojo_sidebar(subreddit, leaders, curr)


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
        f"{curr.year}-{curr.month}-01 00:00:00.000"
    )
    end_timestamp = datetime.fromisoformat(
        f"{curr.year}-{curr.month}-{calendar.monthrange(curr.year, curr.month)[1]} 23:59:59.999"
    )

    comment_urls = check_db_health(reddit, start_timestamp, end_timestamp)

    logging.info(f"Finding scores for {curr.year}-{curr.month}")
    curr += timedelta(hours=24)  # to ensure year/month is for the next month
    leaders = tally_scores(start_timestamp, end_timestamp)

    award_leader(subreddit, leaders, curr)

    publish_wiki(subreddit, leaders, comment_urls, start_timestamp, end_timestamp)


def dojo_cleaner() -> None:
    """
    Performs the workflow of deleting old comments from the db

    Deletes comments which are older than a certain month threshold. This is necessary to ensure db
    does not exceed capacity limits (10000 rows, 1GB) of hobby-dev tier of Heroku PostGreSQL plan.

    Frequency: 5 months (~ 20 weeks)
    """

    conn = connect_to_db()
    cur = conn.cursor()

    cutoff = datetime.now() - timedelta(weeks=WEEK_BUFFER)

    logging.info(f"Deleting comments older than datetime {str(cutoff)}")

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
    """

    # get current dojo post
    dojo = get_tekken_dojo(subreddit)
    new_link = dojo.permalink
    new_full_link = "https://www.reddit.com" + new_link
    logging.debug(f"Dojo permalink: {new_link}")

    # get old link
    curr_welcome_msg_txt = subreddit.mod.settings()["welcome_message_text"]
    m = re.search(
        r"\[\*\*Tekken Dojo\*\*\]\(([^ ]*)\)", curr_welcome_msg_txt, flags=re.MULTILINE
    )
    old_link = m.group(1)
    logging.debug(f"Old Dojo link: {old_link}")

    # Update menu links
    menu = subreddit.widgets.topbar[0]
    for menu_link in menu:
        if menu_link.text == "Tekken Dojo":
            menu_link.mod.update(url=new_full_link)
    logging.info("Updated top bar menu link")

    # Update sidebar widgets (Useful Stuff TextArea + Tekken Dojo ImageWidget)
    for widget in subreddit.widgets.sidebar:
        if isinstance(widget, praw.models.TextArea):
            if "Useful Stuff" in widget.shortName:
                curr_text = widget.text
                new_text = curr_text.replace(old_link, new_link)
                widget.mod.update(text=new_text)
                logging.info("Updated Useful Stuff sidebar link")
        elif isinstance(widget, praw.models.ImageWidget):
            if "Tekken Dojo" in widget.shortName:
                img = widget.data
                img[0].linkUrl = new_full_link
                widget.mod.update(data=img)
                logging.info("Updated Tekken Dojo image link")

    # update welcome message
    new_welcome_msg_txt = curr_welcome_msg_txt.replace(old_link, new_link)
    subreddit.mod.update(welcome_message_text=new_welcome_msg_txt)
    logging.info("Updated welcome message text")
