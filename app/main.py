"""
Runs the streamlit app. 
"""

import time
from typing import List, Union, Dict, Tuple
import re
import urllib

import streamlit as st
import github_reader

import utils
from tweet_templates import ORG_TEMPLATE, USER_TEMPLATE


# Set up page.
OCTOPUS_ICON = "https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/240/twitter/259/octopus_1f419.png"
st.set_page_config(page_title="My year on Github 2020", page_icon=OCTOPUS_ICON)
utils.local_css("static/local_styles.css")

# Create all streamlit components.
st.write(
    '<div class="sticky-header"><a href="https://github.com/jrieke/my-year-on-github/stargazers">Add your ⭐ on Github</a></div>',
    unsafe_allow_html=True,
)
st.image(OCTOPUS_ICON, width=100)
st.title("Tweet your Github stats for 2020 ✨")
username = st.text_input("Your Github username")
clicked = st.button("Show preview")
checkbox_count = st.empty()
_, checkboxes_external = st.beta_columns([0.04, 0.96])
progress_text = st.empty()
progress_bar = st.empty()
tweet_box = st.empty()
# col1, col2 = st.beta_columns(2)
# twitter_button = col1.empty()
# copy_button = col2.empty()
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


def construct_fineprint(runtime: Union[float, None] = None):
    """Show rate limits and runtime of the last action as fineprint."""
    limits = github_reader.rate_limit_info()
    s = """
        <p align="right" id="fineprint">
            Core: {core_remaining} (reset in {core_reset})<br>
            GraphQL: {graphql_remaining} (reset in {graphql_reset})<br>
        """.format(
        **limits
    )
    if runtime is not None:
        s += f"Runtime: {runtime:.2f} s"
    s += "</p>"
    return s


def construct_tweet(stats: Dict) -> str:
    """Generate tweet html text based on `stats`."""
    if stats["is_org"]:
        tweet_html = ORG_TEMPLATE.format(**stats)
    else:
        tweet_html = USER_TEMPLATE.format(**stats)
    return tweet_html


def construct_tweet_button(tweet_html: str) -> str:
    """Generate tweet button html based on tweet html text."""
    link = re.sub("<.*?>", "", tweet_html)  # remove html tags
    link = link.strip()  # remove blank lines at start/end
    link = urllib.parse.quote(link)  # encode for url
    link = "https://twitter.com/intent/tweet?text=" + link
    tweet_button_html = (
        f'<a id="twitter-link" href="{link}" target="_blank" rel="noopener '
        f'noreferrer"><p align="center" id="twitter-button">🐦 Tweet it!</p></a>'
    )
    return tweet_button_html


# def construct_copy_button(tweet_html: str) -> str:
#     # Create template to copy to clipboard.
#     copy_template = re.sub("<.*?>", "", template)  # remove html tags
#     copy_template = copy_template.strip()  # remove blank linkes at start/end
#     copy_template = repr(copy_template)[1:-1]  # explicitly write newlines with \n
#     st.bokeh_chart(copy_button)


fineprint.write(construct_fineprint(), unsafe_allow_html=True)


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
        # about the user (e.g. its repos) but shouldn't take more than 1-3 s.
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

            tweet_html = construct_tweet(stats)
            tweet_box.write(
                tweet_html,
                unsafe_allow_html=True,
            )

            tweet_button_html = construct_tweet_button(tweet_html)
            tweet_button.write(
                tweet_button_html,
                unsafe_allow_html=True,
            )

        progress_bar.empty()
        progress_text.write("")

    except github_reader.UserNotFoundError:
        # Show an error message if the user doesn't exist.
        progress_bar.empty()
        progress_text.write("")
        tweet_box.error(
            f"""
            :octopus: **Octocrap!** Couldn't find user {username}. Did you make a typo 
            or [is this a bug](https://github.com/jrieke/my-year-on-github/issues)?
            """
        )

    # Show runtime of the query and remaining rate limits.
    fineprint.write(
        construct_fineprint(time.time() - start_time), unsafe_allow_html=True
    )

    # copy_text = copy_template.format(**stats)
    # # TODO: This requires streamlit-nightly at the moment, because there's a bug that
    # # shows bokeh charts twice. Remove streamlit-nightly from requirements as soon
    # # as this is resolved. See https://github.com/streamlit/streamlit/issues/2337
    # copy_button_bokeh = bokeh.models.widgets.Button(label="📋 Copy")
    # copy_button_bokeh.js_on_event(
    #     "button_click",
    #     bokeh.models.CustomJS(code=f'navigator.clipboard.writeText("{copy_text}")'),
    # )
    # copy_button.bokeh_chart(copy_button_bokeh)
