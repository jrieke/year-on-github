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

st.set_page_config(page_title="My year on Github 2020", page_icon=OCTOPUS_ICON)
utils.local_css("static/local_styles.css")

st.image(OCTOPUS_ICON, width=100)
"""
# Tweet your Github stats for 2020 ✨
"""
# st.write("<br>", unsafe_allow_html=True)
username = st.text_input("Your Github username")
clicked = st.button("Show preview")
checkbox_count = st.empty()
_, checkboxes_external = st.beta_columns([0.04, 0.96])


def show_checkboxes_external(external_repos):
    include_external = []
    if external_repos:
        count = checkbox_count.checkbox(
            "Count stars of external repos I contributed to"
        )
        if count:
            with checkboxes_external:
                for repo in external_repos:
                    if checkboxes_external.checkbox(repo):
                        include_external.append(repo)
    return include_external


# TODO: Make this a bit nicer, e.g. with a function that plots this dynamically.
# checkbox_count_external = st.empty()
# _, checkboxes_external = st.beta_columns([0.04, 0.96])
# if username or (clicked and username):
# st.write(
#     "<sub>Seems like you contributed to some repos not owned by you! Which ones of these do you want to count?</sub>",
#     unsafe_allow_html=True,
# )
# st.checkbox("ml-tooling/universal-build")
# st.checkbox("ml-tooling/ml-platform")
# st.checkbox("ml-tooling/lazydocs")
# with st.beta_expander("Show 5 more"):
#     st.checkbox("cotect/cotect")
#     st.checkbox("ml-tooling/best-of-update-action")
#     st.checkbox("ml-tooling/best-of-ml-python")
# with st.beta_expander("Include external repos (0 selected)"):
#     st.write(
#         "You contributed to 6 repos from others in 2020! Check all that you want to include in your stats."
#     )

divider = st.empty()
progress_text = st.empty()
progress_bar = st.empty()
# col1, col2 = st.beta_columns([0.15, 0.85])
# avatar = col1.empty()
tweet_box = st.empty()
# col1, col2 = st.beta_columns(2)
# twitter_button = col1.empty()
# copy_button = col2.empty()
tweet_button = st.empty()
fineprint = st.empty()


def show_fineprint(runtime=None):
    limits = github_reader.rate_limit_info()
    s = """
        <p align="right" id="fineprint">
            Core: {core_remaining} (reset in {core_reset})<br>
            GraphQL: {graphql_remaining} (reset in {graphql_reset})<br>
        """.format(**limits)
    if runtime is not None:
        s += f"Runtime: {runtime:.2f} s"
    s += "</p>"
    fineprint.write(s, unsafe_allow_html=True)

show_fineprint()


# TODO: Maybe refactor templating stuff to separate file.
# TODO: Write updating stats in green.
# TODO: Maybe pull the border out of the template.
# TODO: Write URL to hottest repo here? Would be cool to offer sth to click on,
#   but it always shows the link preview in the tweet.
# TODO: Encoding the 🧑‍💻 emoji in a link works in the browser but not on Android. Problem
#   is probably the Twitter app, see if there's a workaround or replace emoji.
user_template = """
<p id="tweet">
My year on Github 2020 🧑‍💻✨ {username}
<br><br>
📬 Commits/Issues/PRs: {contributions}<br>
🏝️ Repos contributed to: {repos_contributed_to}<br>
⭐ New stars: {new_stars}<br>
🔥 Hottest repo: {hottest_repo}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""

org_template = """
<p id="tweet">
Our year on Github 2020 🧑‍💻✨ {username}
<br><br>
⭐ New stars: {new_stars}<br>
🔥 Hottest repo: {hottest_repo}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""


# class CacheTester:

#     # Using st.cache here doesn't work, because it doesn't set self.x = x!!!
#     def __init__(self, x):
#         self.x = x

#     # Using st.cache in her works but note that it also reruns if ANYTHING in self changed!
#     @st.cache
#     def get(self, y):
#         time.sleep(4)
#         print("")
#         return self.x * y


# cache_clicked = st.button("Test the cache")
# if cache_clicked:
#     # st.write(test_cache(3))
#     # st.write(test_cache(2))
#     # st.write(test_cache(3))
#     st.write(CacheTester(1).get(1))
#     st.write(CacheTester(2).get(2))
#     st.write(CacheTester(1).get(1))
#     st.write(CacheTester(3).get(1))


def show_tweet(stats):
    """Generate tweet based on `stats` and show the text plus a "Tweet it!" button."""

    # Create and show tweet.
    if stats["is_org"]:
        tweet = org_template.format(**stats)
    else:
        tweet = user_template.format(**stats)
    tweet_box.write(tweet, unsafe_allow_html=True)
    # avatar.image(stats["avatar_url"], use_column_width=True)
    # avatar.write(
    #     f'<img id="avatar" src="{stats["avatar_url"]}">',
    #     unsafe_allow_html=True,
    # )

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
# @st.cache(hash_funcs={ghapi.core._GhVerb: lambda _: None})
# def stream_stats(username, count_external_repos=None):

#     progress_text.write(f"<sub>Preparing...</sub>", unsafe_allow_html=True)
#     progress_bar.progress(0)

#     for stats, progress, progress_msg in github_reader.stream_stats(
#         username, 2020, count_external_repos
#     ):
#         progress_bar.progress(progress)
#         progress_text.write(f"<sub>{progress_msg}</sub>", unsafe_allow_html=True)
#         show_tweet(stats)
#     return stats


if username or (clicked and username):
    tweet_button.write("")
    # copy_button.write("")
    # divider.write("<br>", unsafe_allow_html=True)

    # TODO: When it's using cached results, the transition is very immediate / hard to
    # notice if trying multiple usernames after another. Make a 1 s delay or a better
    # transition.
    start_time = time.time()
    try:
        # If using cached results, this returns immediately, i.e. we need to show
        # the tweet again below.
        # stats = stream_stats(username, [])


        progress_bar.progress(0)
        progress_text.write(f"Getting user: {username}")
        stats_maker = github_reader.StatsMaker(username, 2020)

        include_external = show_checkboxes_external(stats_maker.external_repos)

        # TODO: Doing this here makes the checkbox disappear for a moment, do it further
        # up. But: user shouldn't select this before stats have finished streaming.
        # count_external_repos = []
        # count_external = checkbox_count_external.checkbox(
        #     "Count stars of external repos I contributed to"
        # )
        # if count_external:
        #     with checkboxes_external:
        #         for full_name in stats["external_repos"]:
        #             if st.checkbox(full_name):
        #                 count_external_repos.append(full_name)

        for stats, progress, progress_msg in stats_maker.stream(include_external):
            progress_bar.progress(progress)
            progress_text.write(progress_msg)
            show_tweet(stats)

        progress_bar.empty()
        progress_text.write("")
        
        # TODO: This is done again here for now because everything is returned in stats.
        #   Get external_repos before querying for stats, then remove this.
        # stats = stream_stats(username, count_external_repos)
        # progress_bar.empty()
        # progress_text.write("")
        # show_tweet(stats)

        # with checkbox_count_external.beta_expander(
        #     "Count stars of external repos I contributed to"
        # ):
        #     for repo in stats["external_repos"]:
        #         st.checkbox(repo)

    # TODO: Re-enable this error in github_reader.
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

    show_fineprint(time.time() - start_time)
