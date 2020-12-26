# [r/Tekken](https://www.reddit.com/r/Tekken/) Bot

Python bot to -

- update the livestream widget for [r/Tekken](https://www.reddit.com/r/Tekken/)
- ~~delete shitposts posted on days other than Shitpost Sunday~~
- implement the dojo system for [r/Tekken](https://www.reddit.com/r/Tekken/)

Based on [r/DotA2](https://www.reddit.com/r/DotA2)'s [sidebar-bot](https://github.com/redditdota/sidebar-bot).
Many thanks to [u/coronaria](https://www.reddit.com/user/coronaria) for pointing me to the source.

## Guide to setting up and running tekken-bot on Heroku

1. Clone this repository using and `cd` into it

    ```
    git clone https://github.com/AbhijeetKrishnan/r-tekken-bot.git
    cd r-tekken-bot
    ```

2. Create an account with [Heroku](https://signup.heroku.com/)
3. Create a [new app](https://dashboard.heroku.com/new-app). You can use any name you want.
4. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) and setup your SSH keys
5. Provision a Postgres database using -

    `heroku addons:create heroku-postgresql:hobby-dev`
6. Login to the Heroku db
    `heroku pg:psql`
7. Create the required database schema and

    ```sql
    create table [table-name] (id varchar, created_utc timestamp, author varchar);
    \q
    ```
8. Create environment variables containing values for the following keys -
    ```
    BOT_USERNAME=tekken-bot
    CLIENT_ID=[reddit-client-id]
    CLIENT_SECRET=[reddit-client-secret]
    PASSWORD=[bot-account-password]
    TWITCH_CLIENT_ID=[twitch-client-id]
    TWITCH_SECRET_ID=[twitch-client-secret]
    tekken=461067
    ```

    You will need to obtain these by registering your application with [Reddit](https://www.reddit.com/wiki/api) and [Twitch](https://dev.twitch.tv/docs/api/).
9. Commit and push the repository to Heroku using git

    ```bash
    git add .
    git commit -am "make it better"
    git push heroku master
    ```
## Guide to testing tekken-bot locally (TODO)

1. Install Postgresql-12
2. Install the Heroku CLI
3. Start the database service

    `sudo service postgresql start`
4. Create a `.env` file containing the following -
    ```bash
    BOT_USERNAME=tekken-bot
    CLIENT_ID=[reddit-client-id]
    CLIENT_SECRET=[reddit-client-secret]
    PASSWORD=[bot-account-password]
    TWITCH_CLIENT_ID=[twitch-client-id]
    TWITCH_SECRET_ID=[twitch-client-secret]
    tekken=461067
    DATABASE_URL=postgres://postgresql?host=/var/run/postgresql&port=5432
    ```
5. Use the Heroku CLI to execute the application locally

    `heroku local`
## Code Structure (TODO)

The code consists of the following files -
- `Procfile`: used by Heroku to start the app
- `requirements.txt`: used by Heroku to initialize the environment
- `runtime.txt`: used by Heroku to initialize the runtime (i.e. Python version)
- `task_runner.py`: the driver code that uses the `schedule` module to schedule all the necessary tasks
- `dojo.py`: implements the dojo workflows of ingestion, award, and clean-up
- `redesign.py`: updates the Livestream widget in the Reddit redesign
- `tasks.py`: implements tasks which don't require a separate module
- `twitch.py`: connects to the Twitch API and returns the list of live Tekken streamers