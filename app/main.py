import random
import time
import streamlit as st
import github_reader
import ghapi
import re
import urllib
import bokeh.models
import utils


OCTOPUS_ICON = "https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/240/twitter/259/octopus_1f419.png"

# ghapi has a bug right now (https://github.com/jrieke/ghapi)
# Install fix via: pip install -U git+https://github.com/jrieke/ghapi
# Also, make sure that fasi is in the newest version because ghapi relies on
# some new functions

st.set_page_config(page_title="My Year On Github", page_icon=OCTOPUS_ICON)
utils.local_css("static/local_styles.css")

st.image(OCTOPUS_ICON, width=100)
"""
# Tweet your Github stats for 2020 ✨
"""
# st.write("<br>", unsafe_allow_html=True)
username = st.text_input("Your Github username")
clicked = st.button("Show preview")
divider = st.empty()
progress_text = st.empty()
progress_bar = st.empty()
tweet_box = st.empty()
# col1, col2 = st.beta_columns(2)
# twitter_button = col1.empty()
# copy_button = col2.empty()
tweet_button = st.empty()
limits = st.empty()


def update_limits():
    limits.write(
        """
        <p align="right" id="rate-limits">
            Core: {core_remaining} (reset in {core_reset})<br>
            GraphQL: {graphql_remaining} (reset in {graphql_reset})
        </p>
        """.format(
            **github_reader.rate_limit_info()
        ),
        unsafe_allow_html=True,
    )


update_limits()


# TODO: Maybe refactor templating stuff to separate file.
# TODO: Write updating stats in green.
# TODO: Maybe pull the border out of the template.
# TODO: Write URL to hottest repo here? Would be cool to offer sth to click on,
#   but it always shows the link preview in the tweet.
# TODO: Twitter doesn't know 🧑‍💻 emoji, maybe replace it.
user_template = """
<p id="tweet">
My year on Github 2020 🧑‍💻✨ {username}
<br><br>
📬 Commits/Issues/PRs: {contributions}<br>
⭐ New stars: {new_stars}<br>
🏝️ New repos: {new_repos}<br>
🔥 Hottest repo (+{hottest_new_stars}): {hottest_full_name}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""

org_template = """
<p id="tweet">
Our year on Github 2020 🧑‍💻✨ {username}
<br><br>
⭐ New stars: {new_stars}<br>
🏝️ New repos: {new_repos}<br>
🔥 Hottest repo (+{hottest_new_stars}): {hottest_full_name}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""


def show_tweet(stats):
    """Generate tweet based on `stats` and show the text plus a "Tweet it!" button."""

    # Create and show tweet.
    if stats["is_org"]:
        tweet = org_template.format(**stats)
    else:
        tweet = user_template.format(**stats)
    tweet_box.write(tweet, unsafe_allow_html=True)

    # Create tweet link and show as button.
    link = re.sub("<.*?>", "", tweet)  # remove html tags
    link = link.strip()  # remove blank lines at start/end
    link = urllib.parse.quote(link)  # encode for url
    link = "https://twitter.com/intent/tweet?text=" + link
    tweet_button.write(
        f'<a id="twitter-link" href="{link}" target="_blank" rel="noopener noreferrer"><p align="center" id="twitter-button">🐦 Tweet it!</p></a>',
        unsafe_allow_html=True,
    )


# Create template to copy to clipboard.
# copy_template = re.sub("<.*?>", "", template)  # remove html tags
# copy_template = copy_template.strip()  # remove blank linkes at start/end
# copy_template = repr(copy_template)[1:-1]  # explicitly write newlines with \n


# st.bokeh_chart(copy_button)
# https://twitter.com/intent/tweet?text=My%20year%20on%20Github%202020%20%26%23129489%3B%26%238205%3B%26%23128187%3B%26%2310024%3B%20jrieke%0A%0A%26%23128236%3B%20Commits/Issues/PRs:%20707%0A%26%2311088%3B%20New%20stars:%20743%0A%26%23127965%3B%26%2365039%3B%20New%20repos:%209%0A%26%23128293%3B%20Hottest%20repo%20(+553):%20jrieke/traingenerator%0A%0AShare%20your%20stats:%20gh2020.jrieke.com%20|%20Built%20by%20@jrieke%20w/%20@streamlit%20@github%20|%20#github2020

# 📅 Busiest Month: February
# 🧑‍💻 User: <a href="https://github.com/{username}">{username}</a><br>
# <a href="https://twitter.com/github">@github</a>


# SPINNER_LINES = [
#     "🔍 Finding your data...",
#     "🧮 Crunching numbers...",
#     "🐙 Counting octocats...",
# ]


# Cache this function, so calling the same username multiple times will not query the
# API again but show the cached results.
# `hash_funcs` disable hashing of the API results, as they cannot be hashed primitively,
# see: https://docs.streamlit.io/en/stable/caching.html
# TODO: This runs all stuff new if there's a tiny change in the code (which doesn't
# impact the API results). Either store values in a proper database or try out disabling
# hashing entirely by passing hash_funcs={github_reader.get_stats: lambda _: None}.
# But this will probably still the delete the cache if I re-deploy.
@st.cache(hash_funcs={ghapi.core._GhVerb: lambda _: None})
def stream_stats(username):
    for stats, progress, progress_msg in github_reader.stream_stats(username, 2020):
        progress_bar.progress(progress)
        progress_text.write(f"<sub>{progress_msg}</sub>", unsafe_allow_html=True)
        show_tweet(stats)
    return stats


if username or (clicked and username):

    tweet_button.write("")
    # copy_button.write("")
    # divider.write("<br>", unsafe_allow_html=True)
    progress_text.write(f"<sub>Preparing...</sub>", unsafe_allow_html=True)
    progress_bar.progress(0)

    start_time = time.time()
    # TODO: When it's using cached results, the transition is very immediate / hard to
    # notice if trying multiple usernames after another. Make a 1 s delay or a better
    # transition.
    try:
        # If using cached results, this returns immediately, i.e. we need to show
        # the tweet again below.
        stats = stream_stats(username)
        progress_bar.empty()
        progress_text.write("")
        show_tweet(stats)
    except github_reader.UserNotFoundError:
        progress_bar.empty()
        progress_text.write("")
        tweet_box.error(
            f":octopus: **Octocrap!** Couldn't find user {username}. Did you make a typo or [is this a bug](https://github.com/jrieke/my-year-on-github/issues)?"
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

    update_limits()
