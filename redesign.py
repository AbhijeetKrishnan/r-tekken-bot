import logging
import time
import re

import praw


def update_sidebar_widget(subreddit, short_name: str, text: str) -> None:
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if short_name in w.shortName:
                if len(text) > 0:
                    w.mod.update(text=text)


def update_sidebar_old(subreddit, section: str, text: str) -> None:
    """
    Updates the sidebar on old Reddit by modifying the config/sidebar wiki page.
    Ref.: https://www.reddit.com/r/redditdev/comments/apqb56/prawusing_praw_to_change_the_sidebardescription/egaj792

    Uses the section param to determine which heading to match, to obtain the content to be replaced
    with the text param.
    """

    logging.info(
        f"Updating sidebar on old Reddit for section {section} with text {text}"
    )
    sidebar = subreddit.wiki["config/sidebar"]
    sidebar_text = sidebar.content_md
    logging.debug(f"Obtained sidebar description: {sidebar_text}")
    old_section_text = re.search(
        f"\*\*\*\n\n\# {section.title()}\n\n([^#]*)\n\*\*\*", sidebar_text, re.MULTILINE
    ).group(1)
    logging.debug(f"Relevant section: {old_section_text}")
    new_section_text = sidebar_text.replace(old_section_text, text)
    logging.debug(f"New sidebar text: {new_section_text}")
    sidebar.edit(new_section_text)
    logging.info("Successfully updated sidebar description")
