import random
import time
import streamlit as st
import github_reader
import ghapi
import re
import urllib


# ghapi has a bug right now (https://github.com/jrieke/ghapi)
# Install fix via: pip install -U git+https://github.com/jrieke/ghapi
# Also, make sure that fasi is in the newest version because ghapi relies on
# some new functions

st.set_page_config(page_title="My Year On Github", page_icon=":octopus:")

"""
# :octopus: My Year On Github

Share your Github stats for 2020 on Twitter. Just enter your Github username below.
"""
username = st.text_input("")
clicked = st.button("Get stats")
divider = st.empty()
progress_text = st.empty()
progress_bar = st.empty()
twitter_link_button = st.empty()
tweet = st.empty()
limits = st.empty()


def update_limits():
    limits.write(
        """
        <sup style="color: gray;">
        Core: {core_remaining} (reset in {core_reset}) | GraphQL: {graphql_remaining} (reset in {graphql_reset})
        </sup>
        """.format(
            **github_reader.rate_limit_info()
        ),
        unsafe_allow_html=True,
    )


update_limits()


# TODO: Write updating stats in green.
template = """
<p style="margin-top: 20px; margin: 50px; padding: 20px; border: 1px solid #4D9FEB; border-radius: 10px;">
My year on Github 2020 🧑‍💻✨ {username}
<br><br>
📬 Commits/Issues/PRs: {contributions}<br>
⭐ New stars: {new_stars}<br>
🏝️ New repos: {new_repos}<br>
🔥 Hottest repo (+{hottest_new_stars}): {hottest_full_name}
<br><br>
Share your stats: <a href="https://yearongh.jrieke.com">yearongh.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""

# Create twitter link template.
twitter_link_template = re.sub("<.*?>", "", template)  # remove html tags
twitter_link_template = twitter_link_template.strip()  # remove blank lines at start/end
twitter_link_template = urllib.parse.quote(
    twitter_link_template, safe="{}"
)  # encode for url
twitter_link_template = "https://twitter.com/intent/tweet?text=" + twitter_link_template


# https://twitter.com/intent/tweet?text=My%20year%20on%20Github%202020%20%26%23129489%3B%26%238205%3B%26%23128187%3B%26%2310024%3B%20jrieke%0A%0A%26%23128236%3B%20Commits/Issues/PRs:%20707%0A%26%2311088%3B%20New%20stars:%20743%0A%26%23127965%3B%26%2365039%3B%20New%20repos:%209%0A%26%23128293%3B%20Hottest%20repo%20(+553):%20jrieke/traingenerator%0A%0AShare%20your%20stats:%20yearongh.jrieke.com%20|%20Built%20by%20@jrieke%20w/%20@streamlit%20@github%20|%20#github2020

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
        progress_text.write(progress_msg)
        tweet.markdown(
            template.format(username=username, **stats), unsafe_allow_html=True,
        )
    return stats


if username or (clicked and username):

    # with st.spinner(random.choice(SPINNER_LINES)):
    twitter_link_button.write("")
    divider.write("---")
    progress_text.write("Preparing...")
    progress_bar.progress(0)

    start_time = time.time()
    # TODO: When it's using cached results, the transition is very immediate / hard to
    # notice if trying multiple usernames after another. Make a 1 s delay or a better
    # transition.
    stats = stream_stats(username)
    tweet.markdown(
        template.format(username=username, **stats), unsafe_allow_html=True,
    )

    progress_text.write(
        f"Finished! Took {time.time() - start_time:.1f} s", unsafe_allow_html=True
    )
    progress_bar.empty()

    twitter_link = twitter_link_template.format(username=username, **stats)
    twitter_link_button.write(
        f'<a href="{twitter_link}" target="_blank" rel="noopener noreferrer">Tweet</a>',
        unsafe_allow_html=True,
    )

    update_limits()

