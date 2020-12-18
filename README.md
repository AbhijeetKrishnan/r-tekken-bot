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