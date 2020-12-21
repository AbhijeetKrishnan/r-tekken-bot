# [r/Tekken](https://www.reddit.com/r/Tekken/) Bot

Python bot to -

- update the livestream widget for [r/Tekken](https://www.reddit.com/r/Tekken/)
- ~~delete shitposts posted on days other than Shitpost Sunday~~
- implement the dojo system for [r/Tekken](https://www.reddit.com/r/Tekken/)

Updating the sidebar only works on the redesign. The job of porting it to old Reddit is not currently being undertaken.

Based on [r/DotA2](https://www.reddit.com/r/DotA2)'s [sidebar-bot](https://github.com/redditdota/sidebar-bot).
Many thanks to [u/coronaria](https://www.reddit.com/user/coronaria) for pointing me to the source.

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

The Dojo Leaderboard system was designed to incentivize users to provide high-quality, helpful
replies to questions in the Tekken Dojo.

The system can be easily hacked by posting low-effort, spam replies to top-level comments in the
Tekken Dojo. Users are encouraged to report such comments as spam; they will be removed and action
will be taken against the repeat offenders.

### Dojo System Implementation Notes

- Flow 1: ingest new comments + update leaderboard sidebar (every day)
- Flow 2: update wiki + award flairs (1st of every month)
- Flow 3: delete old comments from DB (every 5 months ~= 20 weeks)

Is a database needed? Each PRAW call is able to retrieve > 2 months of past comments. I could call
it each time and just use the comments from the month I need without storing them. A database might
be necessary if I want to do yearly leaderboards, but I can't go beyond that due to Heroku db limits
anyways. Also, if activity on the dojo increases, the retrieved comments might only go back to a
month, or less, in which case I'll need a db. I think if I want to scale, I should keep the db.

## Guide to setting up and running tekken-bot on Heroku (TODO)

## Guide to testing tekken-bot locally (TODO)

- Install Postgresql-12
- Install the Heroku CLI
- Start the database service

`sudo service postgresql start`
