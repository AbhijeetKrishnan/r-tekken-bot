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
import twitch

config = configparser.ConfigParser()
config.read("config.txt")

r = None
password = None

def login():
    global r
    global password
    global config

    if password is None:
        password = sys.argv[1]
    r = praw.Reddit(
        client_id=config["reddit.com"]["CLIENT_ID"],
        client_secret=config["reddit.com"]["CLIENT_SECRET"],
        password=password,
        user_agent="r/Tekken Livestream Sidebar Bot by u/pisciatore",
        username=config["reddit.com"]["BOT_USERNAME"]
    )

def update_sidebar():
    print(time.ctime())
    print("UPDATING!")

    tekken = r.subreddit("Tekken")
    redesign.update_sidebar(tekken)

if __name__ == "__main__":
    print("hello")
    login()

    schedule.every(30).seconds.do(update_sidebar)

    while True:
        schedule.run_pending()
        time.sleep(1)
