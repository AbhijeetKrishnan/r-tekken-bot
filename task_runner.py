import configparser
import datetime
import os
import re
import sys
import threading
import time

import praw
import schedule

import redesign
import tasks
import twitch

r = None

def login():
    global r

    config = configparser.ConfigParser()
    config.read("config.txt")

    if config:
        r = praw.Reddit(
            client_id=config["reddit.com"]["CLIENT_ID"],
            client_secret=config["reddit.com"]["CLIENT_SECRET"],
            password=config["reddit.com"]["PASSWORD"],
            user_agent="u/tekken-bot by u/pisciatore",
            username=config["reddit.com"]["BOT_USERNAME"]
        )
    else:
        r = praw.Reddit(
            client_id=os.environ.get("CLIENT_ID"),
            client_secret=os.environ.get("CLIENT_SECRET"),
            password=os.environ.get("PASSWORD"),
            user_agent="u/tekken-bot by u/pisciatore",
            username=os.environ.get("BOT_USERNAME")
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
    print("Starting tasks!")

    tekken = r.subreddit("Tekken")

    print('Updating sidebar...')
    redesign.update_sidebar(tekken)

    # print('Checking for illegal shitposts...')
    # tasks.delete_shitposts(tekken)

if __name__ == "__main__":
    print("Attempting to login...")
    if login():
        print('Exiting application...')
        exit(1)
    
    schedule.every(5).seconds.do(do_tasks)

    while True:
        schedule.run_pending()
        time.sleep(1)
