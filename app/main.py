import random
import time
import streamlit as st
import github_reader
import ghapi


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

    update_limits()

