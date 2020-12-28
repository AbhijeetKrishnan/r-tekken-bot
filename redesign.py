import logging
import time
import re
import traceback

import praw


def update_sidebar_widget(subreddit, short_name: str, text: str) -> None:
    for w in subreddit.widgets.sidebar:
        if isinstance(w, praw.models.TextArea):
            if short_name in w.shortName:
                if len(text) > 0:
                    w.mod.update(text=text)


def update_sidebar_old(
    subreddit, section_title: str, text: str, new_section_title: str = None
) -> None:
    """
    Updates the sidebar on old Reddit by modifying the config/sidebar wiki page.
    Ref.: https://www.reddit.com/r/redditdev/comments/apqb56/prawusing_praw_to_change_the_sidebardescription/egaj792

    Uses the section param to determine which heading to match, to obtain the content to be replaced
    with the text param.
    """

    if not new_section_title:
        new_section_title = section_title

    logging.info(
        f"Updating sidebar on old Reddit for section {section_title} with text {text}"
    )
    sidebar = subreddit.wiki["config/sidebar"]
    sidebar_text = sidebar.content_md
    logging.debug(f"Obtained sidebar description: {sidebar_text}")
    try:
        sections = re.split(r"\*\*\*\*", sidebar_text)
        for idx, section in enumerate(sections):
            if f"# {section_title.title()}" in section:
                relevant_section = section
                relevant_idx = idx
                break
        logging.debug(f"Relevant section: {relevant_section}")
        section_text = f"\n\n# {new_section_title.title()}\n\n{text}\n\n"
        logging.debug(f"New relevant section text: {section_text}")
        sections[relevant_idx] = section_text
        new_sidebar_text = "****".join(sections)
        logging.debug(f"New sidebar text: {new_sidebar_text}")
        sidebar.edit(new_sidebar_text)
        logging.info("Successfully updated sidebar description")
    except Exception:
        logging.error(traceback.format_exc())
