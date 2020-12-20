import random
import streamlit as st
import github_reader


# ghapi has a bug right now (https://github.com/jrieke/ghapi)
# Install fix via: pip install -U git+https://github.com/jrieke/ghapi
# Also, make sure that fasi is in the newest version because ghapi relies on
# some new functions

st.set_page_config(page_title="My Year On Github", page_icon=":octopus:")

SPINNER_LINES = [
    "🔍 Finding your data...",
    "🧮 Crunching numbers...",
    "🐙 Counting octocats...",
]

"""
# :octopus: My Year On Github

Share your Github stats for 2020 on Twitter. Just enter your Github username below.
"""

username = st.text_input("")
# col1, col2, col3 = st.beta_columns(3)
clicked = st.button("Get stats")

if username or clicked:

    with st.spinner(random.choice(SPINNER_LINES)):

        # TODO: Cache the results of this call, so we don't query the same user all
        # over again.
        stats = github_reader.get_stats(username, 2020)

        st.markdown(
            f"""
            <p style="margin-top: 50px; margin: 50px; padding: 20px; border: 1px solid #4D9FEB; border-radius: 10px;">
            My year on <a href="https://twitter.com/github">@github</a> 2020 ✨ 
            <br><br>
            🧑‍💻 User: <a href="https://github.com/{username}">{username}</a><br>
            ➕ Commits/Issues/PRs: {stats['contributions']}<br>
            ⭐ New Stars: {stats['new_stars']}<br>
            🏝️ New Repos: {stats['new_repos']}<br>
            🔥 Hottest Repo (+{stats['hottest_new_stars']} stars): <a href="https://github.com/{stats['hottest_full_name']}">{stats['hottest_full_name']}</a>
            <br><br>
            Share your own: <a href="https://my-year-on-github.jrieke.com">my-year-on-github.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a>
            </p>
            """,
            unsafe_allow_html=True,
        )

