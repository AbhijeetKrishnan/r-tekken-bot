import itertools
from datetime import datetime, timedelta

import praw


def delete_shitposts(subreddit, day=5):
    if day not in range(0, 7):
        print(f'Invalid day of week ({day}). Setting day to Sat (5) instead.')
        day = 5
    if not subreddit:
        print('Subreddit not found')
        return
    for submission in subreddit.new():
        if submission.link_flair_text == 'Shit Post':
            print(submission.title)
            # Check timestamp if it is lies on the given day for all timezones in [-12:00, +14:00]
            timestamp = datetime.fromtimestamp(int(submission.created_utc))
            lies_on_day = False
            for hours, mins in [(-12, 0)] + list(itertools.product(range(-11, 14), (0, 30))) + [(14, 0)]:
                delta = timedelta(hours=hours, minutes=mins)
                new_dt = timestamp + delta
                if new_dt.weekday() == day:
                    lies_on_day = True
            if not lies_on_day:
                # delete post
                print(f'Deleting post: https://www.reddit.com{submission.permalink}')
                submission.mod.remove(reason_id='165uy1jj7q6ux')
