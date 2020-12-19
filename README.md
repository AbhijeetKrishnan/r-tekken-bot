# [r/Tekken](https://www.reddit.com/r/Tekken/) Bot

Python bot to -

- update the livestream widget for [r/Tekken](https://www.reddit.com/r/Tekken/)
- ~~delete shitposts posted on days other than Shitpost Saturday~~
- implement the dojo system for r/Tekken

Updating the sidebar only works on the redesign. The job of porting it to old Reddit is not currently being undertaken.

Based on [r/DotA2](https://www.reddit.com/r/DotA2)'s [sidebar-bot](https://github.com/redditdota/sidebar-bot). Many thanks to [u/coronaria](https://www.reddit.com/user/coronaria) for pointing me to the source.

## Dojo System

The Tekken Dojo is the top-pinned thread of the r/Tekken subreddit which serves as the place for
all Tekken beginners to ask questions. This prevents the front page from getting cluttered with
repetitive posts while giving users interested in answering beginner questions a convenient way to
view all questions together.

Users can earn Dojo points based on *lessons taught* - replies made to beginners asking questions in
the Tekken Dojo. Replies are counted as comments -

- whose parent comment is not the current Tekken Dojo ID (since this can change over time)
- whose parent comment's author is not also the author of the top-level comment on the Dojo
(beginners may ask follow up questions - we don't want to count those, but do want to count replies
to them)

The Tekken Dojo points are logged and displayed in an updating leaderboard in the sidebar. At the
end of the month, the user with the most Dojo points get the title of Dojo Master for that month,
which awards a custom flair.

The final script would use PRAW at the end of each day to scan the comments (need to check the max
amount of comments that can be scanned, and adjust frequency) of scanning based on that), add those
comments to the database (date of creation, author, id, parent id), and at the end of each day
process the data to find the comments made in that month which are replies to top-level comments by
people who are not the original author of the top-level comment, and tabulate the frequencies, and
update the sidebar widget for the leaderboard. Heroku hobby-dev plan offers a 10,000 row limit
(10,000 comments total) and 1 GB storage capacity (assuming a row is int + int + int + str(32) +
str(32) + str(32)) which should be very comfortable. Monthly number of comments seems to be at most
200, so should be able to store 50 months worth of data before having to delete. Need to delete
comments older than X number of months, if we can delete a year or 2 before, would be best (since
year 6 month-old posts get archived anyway.) New BegMegs can be created by automod, and the script
can use a constant or automatically find the newest Beginner Megathread to use (once every 6 months).
Problems will only occur if the sub grows to a large capacity, but I don't think that'll happen soon.

create table dojo_comments (id varchar primary key, parent_id varchar, created_utc timestamp, author varchar)
insert into test (id, parent_id, created_utc, author) values ('ggayril', 'j15bgb', '2020-12-18 15:55:23', 'TheRealCrusader');

## Notes

- Can obtain ~400 top-level comments in total
- Need to obtain their replies as well