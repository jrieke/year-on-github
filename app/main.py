import random
import time
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

if username or (clicked and username):

    "---"

    # with st.spinner(random.choice(SPINNER_LINES)):
    progress_text = st.empty()
    progress_text.write("Preparing...")
    progress_bar = st.progress(0.0)
    tweet = st.empty()

    # TODO: Cache the results of this call, so we don't query the same user all
    # over again.
    start_time = time.time()
    contributions = github_reader.get_contributions(username, 2020)
    # stats = github_reader.get_stats(username, 2020)

    for stats, progress, next_repo_name in github_reader.get_stats(username, 2020):
        # print(stats)
        progress_text.write(f"Parsing repo: {username}/{next_repo_name}")
        progress_bar.progress(progress)
        tweet.markdown(
            template.format(username=username, contributions=contributions, **stats),
            unsafe_allow_html=True,
        )
    progress_text.write(f"Finished! (took {time.time() - start_time:.1f} s)")
    progress_bar.empty()

