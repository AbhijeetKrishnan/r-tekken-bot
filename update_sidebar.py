import datetime
import os
import re
import sys
import threading
import time

import praw
import schedule

import redesign
import twitch

r = None

def login():
    global r

    r = praw.Reddit(
        client_id=os.environ.get("CLIENT_ID"),
        client_secret=os.environ.get("CLIENT_SECRET"),
        password=os.environ.get("PASSWORD"),
        user_agent="r/Tekken Livestream Sidebar Bot by u/pisciatore",
        username=os.environ.get("BOT_USERNAME")
    )

def update_sidebar():
    print(time.ctime())
    print("UPDATING!")

    tekken = r.subreddit("Tekken")
    redesign.update_sidebar(tekken)

if __name__ == "__main__":
    print("Attempting to login...")
    login()
    print("Login successful!")
    
    schedule.every(10).seconds.do(update_sidebar)

    while True:
        schedule.run_pending()
        time.sleep(1)
