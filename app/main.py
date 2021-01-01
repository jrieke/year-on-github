"""
Runs the streamlit app. 
"""

import time
from typing import List
from socket import timeout
from urllib.error import URLError
from fastcore.net import HTTP403ForbiddenError

import streamlit as st

import github_reader
import utils
import templates


# Set up page.
OCTOPUS_ICON = "https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/240/twitter/259/octopus_1f419.png"
st.set_page_config(page_title="Year on Github 2020", page_icon=OCTOPUS_ICON)
utils.local_css("static/local_styles.css")

# Create all streamlit components.
# st.write(
#     '<div class="sticky-header">Built by <a href="https://twitter.com/jrieke">@jrieke</a></div>',
#     unsafe_allow_html=True,
# )
st.image(OCTOPUS_ICON, width=100)
st.title("Tweet your Github stats for 2020 ✨")
username = st.text_input("Your Github username")
clicked = st.button("Show preview")
checkbox_count = st.empty()
_, checkboxes_external = st.beta_columns([0.04, 0.96])
progress_text = st.empty()
progress_bar = st.empty()
error_box = st.beta_container()
tweet_box = st.empty()
# col1, col2 = st.beta_columns(2)
# twitter_button = col1.empty()
# copy_button = col2.empty()
star_text = st.write(
    '<p align="left"><sub>If you like this site, please <a target="_blank" rel="noopener noreferrer" href="https://github.com/jrieke/my-year-on-github/stargazers">give it a ⭐ on Github</a> :)</sub></p>',
    unsafe_allow_html=True,
)
tweet_button = st.empty()
fineprint = st.empty()


def show_checkboxes_external(external_repos: List[str]) -> List[str]:
    """Show checkboxes to select external repos that should be counted."""
    include_external = []
    if external_repos:
        # Need to set custom key here so this doesn't keep state when querying for
        # different users.
        count = checkbox_count.checkbox(
            "Count stars of external repos I contributed to", key="count" + username
        )
        if count:
            with checkboxes_external:
                st.write(
                    "<sub><i>Sorted by number of commits, highest first</i></sub>",
                    unsafe_allow_html=True,
                )
                for repo in external_repos[:5]:
                    # Need to set custom key here so this doesn't keep state when
                    # querying for different users (only happens if they contributed to
                    # the same repo).
                    if st.checkbox(repo, key="external" + username + repo):
                        include_external.append(repo)
                if len(external_repos) > 5:
                    with st.beta_expander("Show more"):
                        for repo in external_repos[5:]:
                            if st.checkbox(repo, key="external" + username + repo):
                                include_external.append(repo)
    return include_external


fineprint.write(templates.fineprint(), unsafe_allow_html=True)


# TODO: The 2nd part is actually a bit useless here. Clicking the button actually
#   doesn't change a critical value but it just updates the page so the username
#   value is passed on properly.
if username or (clicked and username):

    # Hide some components in case they are already shown but a new username is queried.
    tweet_button.write("")
    checkbox_count.empty()
    checkboxes_external.empty()
    # copy_button.write("")

    start_time = time.time()
    try:
        # Create a StatsMaker instance. This already queries some basic information
        # about the user (e.g. its repos) from the Github API but shouldn't take more
        # than 1-3 s.
        progress_bar.progress(0)
        progress_text.write(
            f'<p id="progress-text">Getting user: {username}</p>',
            unsafe_allow_html=True,
        )
        stats_maker = github_reader.StatsMaker(username, 2020)

        # Show a checkbox for each external repo that the user contributed to.
        include_external = show_checkboxes_external(stats_maker.external_repos)

        # Stream stats from stats_maker, generate tweet from template and show it.
        # The `stream` method is a generator which yields intermediate results.
        for stats, progress, progress_msg in stats_maker.stream(include_external):
            progress_bar.progress(progress)
            progress_text.write(
                f'<p id="progress-text">{progress_msg}</p>', unsafe_allow_html=True
            )

            tweet_html = templates.tweet(stats)
            tweet_box.write(tweet_html, unsafe_allow_html=True)

            tweet_button_html = templates.tweet_button(tweet_html)
            tweet_button.write(tweet_button_html, unsafe_allow_html=True)

        progress_bar.empty()
        progress_text.write("")

    except github_reader.UserNotFoundError:
        # Show an error message if the user doesn't exist.
        progress_bar.empty()
        progress_text.write("")
        error_box.error(
            f"""
            :octopus: **Octocrap!** Couldn't find user {username}. Did you make a typo 
            or [is this a bug](https://github.com/jrieke/my-year-on-github/issues)?
            """
        )
    except (timeout, URLError):  # these are the same
        # Show an error message if there's a HTTP timeout. This can happen some time if
        # we made lots of API requests in a few minutes.
        error_box.error(
            f"""
            :octopus: **Octocrap!** Got a timeout from the Github API – this can happen
            if you have large repos or too many people are using this site at the same 
            time :/ You can just reload this site and enter your username again,
            the crawler will continue where it stopped. 
            
            If this keeps happening, 
            [open an issue](https://github.com/jrieke/my-year-on-github/issues).
            """
        )
    except HTTP403ForbiddenError:
        # Show an error message if we couldn't access the API - probably because we
        # reached the rate limit.
        error_box.error(
            f"""
            :octopus: **Octocrap!** Couldn't access the Github API – this can happen
            if too many people are using this site at the same time :/ Try again
            later or [open an issue](https://github.com/jrieke/my-year-on-github/issues).
            """
        )
    except Exception as e:
        # Show an error message for any unexpected exceptions.
        # Do not reset progress bar here, so the user can report when it stopped.
        # TODO: Fix margins for error_box, especially if tweet_box is also shown.
        error_box.error(
            f"""
            :octopus: **Octocrap!** Something went wrong. Please
            [open an issue on Github](https://github.com/jrieke/my-year-on-github/issues)
            and report the error printed below.
            """
        )
        error_box.write(e)

    # Show runtime of the query and remaining rate limits.
    fineprint.write(
        templates.fineprint(time.time() - start_time), unsafe_allow_html=True
    )
