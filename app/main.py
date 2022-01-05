"""
Runs the streamlit app. 
"""

import time
from typing import List
from socket import timeout
from urllib.error import URLError
from fastcore.net import HTTP403ForbiddenError
import traceback
import warnings

import streamlit as st

import github_reader
import utils
import templates


# Set up page.
st.set_page_config(page_title="Year on Github 2021", page_icon="🐙")
utils.local_css("static/local_styles.css")

if "show_all_repos" not in st.session_state:
    st.session_state["show_all_repos"] = False


def show_more():
    st.session_state["show_all_repos"] = True


def show_less():
    st.session_state["show_all_repos"] = False


if "preview_shown" not in st.session_state:
    st.session_state["preview_shown"] = False


# Create all streamlit components.
st.write("")
st.write(
    '<img width=100 src="https://emojipedia-us.s3.amazonaws.com/source/skype/289/squid_1f991.png" style="margin-left: 5px; filter: hue-rotate(230deg) brightness(1.1);">',
    unsafe_allow_html=True,
)
st.title("Tweet your Github stats for 2021")
st.write(
    """
    [![Star](https://img.shields.io/github/stars/jrieke/year-on-github.svg?logo=github&style=social)](https://gitHub.com/jrieke/year-on-github)
    &nbsp[![Follow](https://img.shields.io/twitter/follow/jrieke?style=social)](https://www.twitter.com/jrieke)
    """
)
st.write("")
username = st.text_input("Your Github user/org name")
if not username:
    st.button("Show preview")
    # This button doesn't do anything, the page updates anyway when clicked.
    # But it reassures the user that it's just a preview and we don't tweet immediately.

progress_text = st.empty()
progress_bar = st.empty()
error_box = st.container()
tweet_box = st.empty()
checkboxes_external = st.container()
tweet_button = st.empty()

# Show tweets from Twitter bot (@gh2021_bot). The content of the iframe is hosted in
# a small Github pages site from this repo: https://github.com/jrieke/year-on-github-tweet-wall
st.write("---")
st.markdown(
    """
    <div style="display: flex; width: 100%; height: 100%; flex-direction: column; overflow: hidden;">
        <iframe height="1000" style="margin-left: -15px;" src="https://www.jrieke.com/year-on-github-tweet-wall/"></iframe>
    </div>
    """,
    unsafe_allow_html=True,
)

fineprint = st.empty()


def show_checkboxes_external(external_repos: List[str]) -> List[str]:
    """Show checkboxes to select external repos that should be counted."""
    include_external = []
    if external_repos:
        # Need to set custom key here so this doesn't keep state when querying for
        # different users.
        with checkboxes_external:
            count = st.checkbox(
                "Count stars of external repos I contributed to", key="count" + username
            )
            if count:
                _, col = st.columns([0.06, 0.94])
                with col:
                    st.caption("Repo with most commits first")
                    for repo in external_repos[:5]:
                        # Need to set custom key here so this doesn't keep state when
                        # querying for different users (only happens if they contributed to
                        # the same repo).
                        if st.checkbox(repo, key="external" + username + repo):
                            include_external.append(repo)
                    if len(external_repos) > 5:
                        if st.session_state["show_all_repos"]:
                            for repo in external_repos[5:]:
                                if st.checkbox(repo, key="external" + username + repo):
                                    include_external.append(repo)
                            st.button("Show less", on_click=show_less)
                        else:
                            st.button("Show more", on_click=show_more)
    return include_external


fineprint.write(templates.fineprint(), unsafe_allow_html=True)


def print_error(e, print_traceback=False):
    """Logs error to stdout, so it's not only shown to the user through streamlit."""
    print()
    print("=" * 80)
    print(f"ERROR for user {username}:", e)
    if print_traceback:
        print()
        traceback.print_exc()
    print("=" * 80)
    print()


if username:

    # Hide some components in case they are already shown but a new username is queried.
    tweet_button.write("")

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
        stats_maker = github_reader.StatsMaker(username, 2021)

        # Show a checkbox for each external repo that the user contributed to.
        include_external = show_checkboxes_external(stats_maker.external_repos)

        # Stream stats from stats_maker, generate tweet from template and show it.
        # The `stream` method is a generator which yields intermediate results.
        with warnings.catch_warnings(record=True) as w:
            for stats, progress, progress_msg in stats_maker.stream(include_external):
                progress_bar.progress(progress)
                progress_text.write(
                    f'<p id="progress-text">{progress_msg}</p>', unsafe_allow_html=True
                )

                tweet_html = templates.tweet(stats)
                tweet_box.write(tweet_html, unsafe_allow_html=True)

                tweet_button_html = templates.tweet_button(tweet_html, username)
                tweet_button.write(tweet_button_html, unsafe_allow_html=True)

            # Print warning if any was catched.
            if w:
                error_box.warning(w[0].message)
                print("=" * 80)
                print(f"WARNING for user {username}:", w[0].message)
                print("=" * 80)

        progress_bar.empty()
        progress_text.empty()

    except github_reader.UserNotFoundError as e:
        # Show an error message if the user doesn't exist.
        progress_bar.empty()
        progress_text.write("")
        error_box.error(
            f"""
            :octopus: **Octocrap!** Couldn't find user {username}. Did you make a typo 
            or [is this a bug](https://github.com/jrieke/my-year-on-github/issues)?
            """
        )
        print_error(e)
    except (timeout, URLError) as e:  # these are the same
        # Show an error message if there's a HTTP timeout. This can happen some time if
        # we made lots of API requests in a few minutes.
        error_box.error(
            """
            :octopus: **Octocrap!** Got a timeout from the Github API – this can happen
            if you have large repos or too many people are using this site at the same 
            time :/ You can just reload this site and enter your username again,
            the crawler will continue where it stopped. 
            
            If this keeps happening, 
            [open an issue](https://github.com/jrieke/my-year-on-github/issues).
            """
        )
        print_error(e)
    except HTTP403ForbiddenError as e:
        # Show an error message if we couldn't access the API - probably because we
        # reached the rate limit.
        error_box.error(
            """
            :octopus: **Octocrap!** Couldn't access the Github API – this can happen
            if too many people are using this site at the same time :/ Try again
            later or [open an issue](https://github.com/jrieke/my-year-on-github/issues).
            """
        )
        print_error(e)
    except Exception as e:
        # Show an error message for any unexpected exceptions.
        # Do not reset progress bar here, so the user can report when it stopped.
        error_box.error(
            """
            :octopus: **Octocrap!** Something went wrong. Please
            [open an issue on Github](https://github.com/jrieke/my-year-on-github/issues)
            and report the error printed below.
            """
        )
        error_box.write(e)
        print_error(e, print_traceback=True)

    # Show runtime of the query and remaining rate limits.
    fineprint.write(
        templates.fineprint(time.time() - start_time), unsafe_allow_html=True
    )

# Tracking pixel to count number of visitors.
if "TRACKING_NAME" in st.secrets:
    st.write(
        f"![](https://jrieke.goatcounter.com/count?p={st.secrets['TRACKING_NAME']})"
    )
