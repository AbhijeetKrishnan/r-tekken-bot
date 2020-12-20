import datetime
import os
import re
import sys
import threading
import time

import praw
import schedule

import dojo
import redesign
import tasks
import twitch

r = None

# TODO: use logging module everywhere instead of print statements

def login():
    global r

    r = praw.Reddit(
        client_id=os.environ['CLIENT_ID'],
        client_secret=os.environ['CLIENT_SECRET'],
        password=os.environ['PASSWORD'],
        user_agent='u/tekken-bot by u/pisciatore',
        username=os.environ['BOT_USERNAME']
    )
    try:
        print(r.user.me())
        print('Login successful!')
        return 0
    except Exception:
        print('Login unsuccessful')
        return 1

if __name__ == '__main__':
    print('Attempting to login...')
    if login():
        print('Exiting application...')
        exit(1)

    tekken = r.subreddit('Tekken')
    
    print(time.ctime())
    print('Starting tasks!')

    schedule.every(30).seconds.do(redesign.update_sidebar, subreddit=tekken)
    # schedule.every(30).seconds.do(tasks.delete_shitposts, subreddit=tekken)
    schedule.every(60).seconds.do(dojo.dojo_leaderboard, subreddit=tekken)
    schedule.every(1).day.at('00:00:00').do(dojo.dojo_award, subreddit=tekken)
    schedule.every(20).weeks.do(dojo.dojo_cleaner)

    while True:
        schedule.run_pending()
        time.sleep(1)
