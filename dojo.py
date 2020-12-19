"Implements tasks required for the Dojo system on r/Tekken."

import os
from datetime import datetime

import praw
import psycopg2
from psycopg2 import sql
import schedule

TABLE_NAME = 'dojo_comments'

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

def ingest_new(submission, conn):
    """
    Ingest all new comments made on the submmission into the database.
    Assumes table TABLE_NAME is already created
    """

    cur = conn.cursor()
    while True:
        try:
            submission.comments.replace_more()
            break
        except Exception:
            print("Handling replace_more exception")
            sleep(1)

    for comment in submission.comments:
        if comment.author:
            author = comment.author.name
        else:
            author = '[deleted]'
        record = (comment.id, comment.parent_id, datetime.fromtimestamp(comment.created_utc), author)
        print('Comment record: ({}, {}, {}, {})'.format(*record))
        try:
            cur.execute(sql.SQL('INSERT INTO {} (id, parent_id, created_utc, author) VALUES (%s, %s, %s, %s)').format(sql.Identifier(TABLE_NAME)), 
                record)
        except psycopg2.errors.UniqueViolation:
            print(f'Attempted to insert duplicate key {comment.id}')
            conn.rollback()
            continue

    conn.commit()
    cur.close()

# TODO: go through database and check if comment still exists (called before tallying final scores)

def dojo_runner(subreddit):
    print('Connecting to db...')
    conn = connect_to_db()
    print('Connected to db!')
    print('Retrieving Tekken Dojo...')
    dojo = get_tekken_dojo(subreddit)
    print('Obtained Tekken Dojo!')
    print('Ingesting new comments...')
    ingest_new(dojo, conn)
    print('Successfully ingested new comments!')
    print('Closing connection...')
    conn.close()