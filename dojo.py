"Implements tasks required for the Dojo system on r/Tekken."

import calendar
import logging
import os
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta

import praw
import psycopg2
import schedule
from psycopg2 import sql

TABLE_NAME = (
    "dojo_comments"  # the name of the table where Tekken Dojo comments are stored
)
LEADERBOARD_SIZE = 5  # the top-k commenters will be displayed
WEEK_BUFFER = 20  # delete comments from the database older than these many weeks
DOJO_MASTER_FLAIR_ID = "cc570168-4176-11eb-abb3-0e92e4d477f5"


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


def ingest_new(submission, stream):
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
        for comment in stream:
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


def tally_scores(start_timestamp, end_timestamp):
    """
    Go through database to produce count of final scores + comment_ids for comments lying in range
    [start_timestamp, end_timestamp]
    """

    logging.debug("Connecting to db...")
    conn = connect_to_db()
    logging.debug("Connected to db!")
    cur = conn.cursor()

    cur.execute(
        sql.SQL(
            """
                        SELECT author, count(*)
                        FROM {}
                        WHERE created_utc BETWEEN %s AND %s
                        GROUP BY author
                        ORDER BY count(*) DESC
                        """
        ).format(sql.Identifier(TABLE_NAME)),
        (start_timestamp, end_timestamp),
    )

    leaders = []
    while len(leaders) < LEADERBOARD_SIZE:
        record = cur.fetchone()
        if not record:  # error, or no one commented!?
            break
        if record[0] != "[deleted]":
            leaders.append(record)

    cur.close()
    logging.debug("Closing connection...")
    conn.close()
    logging.info(f"Leaderboard for {start_timestamp.month}: {leaders}")
    return leaders


def check_db_health(reddit, start_timestamp, end_timestamp):
    """
    Ensures that every comment in the database in the range [start_timestamp, end_timestamp] still exists i.e. has not been deleted.

    Goes through every comment in the database in the given range and checks if the comment body is present. If not, it
    is deleted.
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


def get_leaderboard(leaders):
    """
    Generate the Markdown text to display in the Dojo Leaderboard TextArea widget. Only visible in
    the redesign.
    """

    text = "Rank | User | Dojo Points \n"
    text += ":-: | :- | :-: \n"
    for rank, item in enumerate(leaders):
        text += f"{rank + 1} | u/{item[0]} | {item[1]}\n"
    text += "***\n"
    text += f"^(Last updated: {time.ctime()} UTC by u/tekken-bot)\n"
    logging.info(f"Leaderboard widget text - \n{text}")
    return text


def update_dojo_sidebar(subreddit, leaders, dt):
    """
    Update the Dojo Leaderboard TextArea widget with the current leaderboard contents. Also use the
    current datetime to update the widget title.
    """

    year = "'" + str(dt.year)[-2:]
    month = calendar.month_name[dt.month][:3]
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if "Dojo Leaderboard" in w.shortName:
                text = get_leaderboard(leaders)
                new_short_name = f"Dojo Leaderboard ({month} {year})"
                if len(text) > 0:
                    logging.info(
                        f"Updating Dojo Leaderboard widget shortName as {new_short_name}"
                    )
                    w.mod.update(shortName=new_short_name, text=text)


def award_leader(subreddit, leader, dt):
    """
    Awards user with Dojo Master flair and removes flair from previous Dojo Master.

    Flair is appended to end of user's existing flair with '| Dojo Master (Mon)'.
    Previous Dojo Master's Flair is changed to Mokujin with their original flair text restored.
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
            break

    # Set flair of leader
    original_flair_text = next(subreddit.flair(leader[0]))["flair_text"]
    logging.debug(
        f"Original flair text obtained for {leader[0]} is {original_flair_text}"
    )
    new_flair_text = f"{original_flair_text} | {dojo_flair_text}"
    subreddit.flair.set(
        leader[0], text=new_flair_text, flair_template_id=DOJO_MASTER_FLAIR_ID
    )
    logging.info(f"Set flair of {leader[0]} as {new_flair_text}")


def publish_wiki(subreddit, leaders, dt):
    """
    Publishes the results of the leaderboard for the month's wiki.

    Each (year, month) has a separate page for it, where each page is a table listing the top 5 dojo
    point winners, along with a list of links to the comments which earned them those points.
    """

    pass


def dojo_leaderboard(subreddit, stream):
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

    logging.info(f"Finding scores for {curr.year}-{curr.month}")

    leaders = tally_scores(start_timestamp, end_timestamp)
    update_dojo_sidebar(subreddit, leaders, curr)


def dojo_award(reddit, subreddit):
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

    check_db_health(reddit, start_timestamp, end_timestamp)

    logging.info(f"Finding scores for {curr.year}-{curr.month}")
    curr += timedelta(hours=24)  # to ensure year/month is for the next month
    leaders = tally_scores(start_timestamp, end_timestamp)

    award_leader(subreddit, leaders[0], curr)

    publish_wiki(subreddit, leaders, curr)


def dojo_cleaner():
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
