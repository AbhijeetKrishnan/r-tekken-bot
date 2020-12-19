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

def do_tasks():
    print(time.ctime())
    print('Starting tasks!')

    tekken = r.subreddit('Tekken')

    #print('Updating sidebar...')
    #redesign.update_sidebar(tekken)

    # print('Checking for illegal shitposts...')
    # tasks.delete_shitposts(tekken)

if __name__ == '__main__':
    print('Attempting to login...')
    if login():
        print('Exiting application...')
        exit(1)
    
    #schedule.every(30).seconds.do(do_tasks)

    tekken = r.subreddit('Tekken')

    schedule.every(60).seconds.do(dojo.dojo_runner, subreddit=tekken)

    while True:
        schedule.run_pending()
        time.sleep(1)
