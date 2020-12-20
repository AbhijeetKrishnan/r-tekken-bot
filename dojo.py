"Implements tasks required for the Dojo system on r/Tekken."

import calendar
import logging
import os
import traceback
from collections import defaultdict
from datetime import datetime, timedelta

import praw
import psycopg2
import schedule
from psycopg2 import sql

TABLE_NAME = 'dojo_comments' # the name of the table where Tekken Dojo comments are stored
LEADERBOARD_SIZE = 5 # the top-k commenters will be displayed
WEEK_BUFFER = 20 # delete comments from the database older than these many weeks

def connect_to_db():
    "Connect to database and return the connection object."

    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def get_tekken_dojo(subreddit):
    """
    The Tekken Dojo is assumed to be the first pinned post of the subreddit.

    Returns: the Submission object of the Tekken Dojo post
    """

    tekken_dojo = subreddit.sticky()
    return tekken_dojo

def ingest_new(submission):
    """
    Ingest all new comments made on the submmission into the database.
    Assumes table TABLE_NAME is already created
    """

    # TODO: retrieves ~1400 comments in each call from ~2 months back. If called every day, would
    # retrieve many duplicate comments which would not be inserted into the db. Any way to improve
    # this to only retrieve newer comments, or insert new records into the db?
    # Check out the SubmissionStream object

    logging.debug('Connecting to db...')
    conn = connect_to_db()
    logging.debug('Connected to db!')
    cur = conn.cursor()

    records = 0 # to count total number of comments inserted into the db

    while True:
        try:
            submission.comments.replace_more()
            break
        except Exception:
            logging.warning("Handling replace_more exception")
            sleep(1)

    for comment in submission.comments.list(): # ref.: https://praw.readthedocs.io/en/latest/tutorials/comments.html

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
            author = '[deleted]'

        record = (comment.id, datetime.fromtimestamp(comment.created_utc), author)
        logging.debug('Comment record: ({}, {}, {})'.format(*record))
        try:
            cur.execute(sql.SQL("""
            INSERT INTO {} (id, created_utc, author) 
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """).format(sql.Identifier(TABLE_NAME)), 
                record)
            if cur.rowcount == 0:
                logging.debug('Comment already exists in db!')
            else:
                logging.debug('Inserted comment into db')
            records += cur.rowcount
        except:
            traceback.print_exception()
            conn.rollback()
            continue
    
    conn.commit()
    cur.close()
    logging.debug('Closing connection...')
    conn.close()
    return records

def tally_scores(start_timestamp, end_timestamp):
    """
    Go through database to produce count of final scores + comment_ids for comments lying in range
    [start_timestamp, end_timestamp]
    """

    logging.debug('Connecting to db...')
    conn = connect_to_db()
    logging.debug('Connected to db!')
    cur = conn.cursor()

    cur.execute(sql.SQL("""
                        SELECT author, count(*)
                        FROM {}
                        WHERE created_utc BETWEEN %s AND %s
                        GROUP BY author
                        ORDER BY count(*) DESC
                        """).format(sql.Identifier(TABLE_NAME)), (start_timestamp, end_timestamp))

    leaders = []
    while len(leaders) < LEADERBOARD_SIZE:
        record = cur.fetchone()
        if not record: # error, or no one commented!?
            break
        if record[0] != '[deleted]':
            leaders.append(record)

    cur.close()
    logging.debug('Closing connection...')
    conn.close()
    logging.info(f'Leaderboard for {start_timestamp.month}: {leaders}')
    return leaders

def get_leaderboard(leaders):
    """
    Generate the Markdown text to display in the Dojo Leaderboard TextArea widget. Only visible in
    the redesign.
    """
 
    text = 'User | Dojo Points \n'
    text += ':- | :-: \n'
    for item in leaders:
        text += f'u/{item[0]} | {item[1]} \n'
    text += "***\n^(This widget is auto-updated by u/tekken-bot developed by u/pisciatore.)" # credit myself
    logging.info(f'Leaderboard widget text - \n{text}')
    return text

def update_dojo_sidebar(subreddit, leaders, cur_dt):
    """
    Update the Dojo Leaderboard TextArea widget with the current leaderboard contents. Also use the
    current datetime to update the widget title.
    """

    year = "'" + str(cur_dt.year)[-2:]
    month = calendar.month_name[cur_dt.month][:3]
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if 'Dojo Leaderboard' in w.shortName:
                text = get_leaderboard(leaders)
                new_short_name = f'Dojo Leaderboard ({month} {year})'
                if len(text) > 0:
                    logging.info(f'Updating Dojo Leaderboard widget shortName as {new_short_name}')
                    w.mod.update(shortName=new_short_name, text=text)

def dojo_leaderboard(subreddit):
    """
    Performs the workflow of updating the dojo leaderboard. This includes -

    1. ingesting new comments from the Tekken Dojo and adding them to the db
    2. calculating the leaderboard by querying the db
    3. publishing the results to the sidebar widget

    Frequency: 1 day
    """

    logging.info('Retrieving Tekken Dojo...')
    dojo = get_tekken_dojo(subreddit)
    logging.info('Obtained Tekken Dojo!')
    logging.info('Ingesting new comments...')
    total_comments = ingest_new(dojo)
    logging.info(f'Successfully ingested {total_comments} new comments!')

    # Find (year, month) to tally scores for
    curr = datetime.now()
    start_timestamp = datetime.fromisoformat(f'{curr.year}-{curr.month}-01 00:00:00.000')
    end_timestamp = datetime.fromisoformat(f'{curr.year}-{curr.month}-{calendar.monthrange(curr.year, curr.month)[1]} 23:59:59.999')

    logging.info(f'Finding scores for {curr.year}-{curr.month}')

    leaders = tally_scores(start_timestamp, end_timestamp)
    update_dojo_sidebar(subreddit, leaders, curr)

def dojo_award(subreddit):
    """
    Performs the workflow of publishing the winner and awarding them at the end of each month. This
    includes -
    1. publishing the leaderboard results to the wiki (each of the top 5 with links to the comments
       included in their score)
    2. awarding custom flairs to the leader

    Frequency: 1st of every month
    """

    # Exit from function if not the 1st of the month
    # Ref.: https://stackoverflow.com/a/57221649
    if datetime.now().day != 1:
        logging.info('Not 1st of the month, skipping award workflow...')
        return
    
    pass

def dojo_cleaner():
    """
    Performs the workflow of deleting old comments from the db

    Deletes comments which are older than a certain month threshold. This is necessary to ensure db
    does not exceed capacity limits of hobby-dev tier of Heroku PostGreSQL plan.

    Frequency: 5 months (~ 20 weeks)
    """

    conn = connect_to_db()
    cur = conn.cursor()

    cutoff = datetime.now() - timedelta(weeks=WEEK_BUFFER)

    logging.info(f'Deleting comments older than datetime {str(cutoff)}')

    cur.execute(sql.SQL("""
    DELETE FROM {}
    WHERE created_utc < %s
    """.format(sql.Identifier(TABLE_NAME))), (cutoff))

    logging.info(f'Deleted {cur.rowcount} rows')

    conn.commit()
    cur.close()
    conn.close()
