"""A stand-alone script to update the r/Tekken calendar for Tekken 7 tournaments on smash.gg. Run once
a year"""

import logging
import os
import pickle
import traceback
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from dotenv import load_dotenv  # LOCAL
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

# LOCAL
load_dotenv()
auth_token = os.environ["SMASHGG"]
gcal_id = os.environ["GCAL"]

PER_PAGE = 999
TEKKEN7_ID = 17

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_tournaments(
    before=datetime.now() + timedelta(days=365),
) -> List[Tuple[str, datetime, datetime, Optional[str]]]:
    """
    Get a list of all future Tekken 7 tournaments on smash.gg before a certain date
    """
    # TODO: traverse tournament list for individual events and add those instead
    tournaments_list = []

    transport = RequestsHTTPTransport(
        url="https://api.smash.gg/gql/alpha",
        headers={
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        },
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)

    query_str = """
        query TournamentsByVideogame($perPage: Int!, $videogameId: ID!) {{
            tournaments(query: {{
                perPage: $perPage
                page: {}
                sortBy: "startAt asc"
                filter: {{
                    afterDate: {}
                    beforeDate: {}
                    videogameIds: [
                        $videogameId
                    ]
                }}
            }}) {{
                nodes {{
                    name
                    slug
                    startAt
                    endAt
                    streams {{
                        streamName
                        streamSource
                    }}
                }}
            }}
        }}
        """

    params = {
        "perPage": PER_PAGE,
        "videogameId": TEKKEN7_ID,  # https://docs.google.com/spreadsheets/d/1l-mcho90yDq4TWD-Y9A22oqFXGo8-gBDJP0eTmRpTaQ/edit?usp=sharing
    }
    page = 1
    while True:
        query = gql(
            query_str.format(
                page, int(datetime.now().timestamp()), int(before.timestamp())
            )
        )
        logging.debug(f"Generated query: \n{query}")

        try:
            result = client.execute(query, variable_values=params)
        except:
            logging.error(traceback.format_exc())

        data = result["tournaments"]["nodes"]
        if not data:
            logging.debug("Responses exhausted")
            break
        logging.info(f"Response length: {len(data)}")
        for tournament in data:
            name = tournament["name"]
            url = "https://smash.gg/" + tournament["slug"]
            startAt = datetime.fromtimestamp(tournament["startAt"])
            endAt = datetime.fromtimestamp(tournament["endAt"])
            streams = tournament["streams"]
            twitch_url = None
            if streams:
                for stream in streams:
                    stream_name = stream["streamName"]
                    source = stream["streamSource"]
                    if source == "TWITCH":
                        twitch_url = "https://twitch.tv/" + stream_name
            tournaments_list.append((name, url, startAt, endAt, twitch_url))
        if len(data) < 999:
            logging.info(
                f"Response length ({len(data)}) less than per page limit ({PER_PAGE}). Exiting loop..."
            )
            break
        page += 1
    return tournaments_list


def add_to_gcal(
    tournaments: List[Tuple[str, datetime, datetime, Optional[str]]],
    calendarId: str = "primary",
) -> None:
    """
    Add events defined by tournament_list to calendar_id while avoiding duplicate entries
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)
    for tournament in tournaments:
        event = {
            "summary": f"[{tournament[0]}]({tournament[1]})",
            "location": f"[Twitch]({tournament[4]})",
            "start": {
                "dateTime": f"{tournament[2].replace(microsecond=0).isoformat()}",
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": f"{tournament[3].replace(microsecond=0).isoformat()}",
                "timeZone": "UTC",
            },
        }
        if not tournament[4]:
            event.pop("location", None)
        logging.info(event)
        event = service.events().insert(calendarId=calendarId, body=event).execute()
        logging.info("Event created: %s" % (event.get("htmlLink")))


if __name__ == "__main__":
    tournaments_list = get_tournaments()
    add_to_gcal(tournaments_list, gcal_id)
