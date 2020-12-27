# Define templates for the tweet (separate for user and org). These will be filled
# with the stats later and shown in the box.
# TODO: Maybe refactor templating stuff to separate file.
# TODO: Write updating stats in green.
# TODO: Write URL to hottest repo here? Would be cool to offer sth to click on,
#   but it always shows the link preview in the tweet.
# TODO: Encoding the 🧑‍💻 emoji in a link works in the browser but not on Android. Problem
#   is probably the Twitter app, see if there's a workaround or replace emoji.
USER_TEMPLATE = """
<p id="tweet">
My year on Github 2020 🧑‍💻✨ {username}
<br><br>
📬 Commits/Issues/PRs: {contributions}<br>
🏝️ Repos contributed to: {repos_contributed_to}<br>
⭐ New stars: <span style='background-color: #FFFFFF'>{new_stars}</span><br>
🔥 Hottest repo: {hottest_repo}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""

ORG_TEMPLATE = """
<p id="tweet">
Our year on Github 2020 🧑‍💻✨ {username}
<br><br>
⭐ New stars: <span style='background-color: #FFFFFF'>{new_stars}</span><br>
🔥 Hottest repo: {hottest_repo}
<br><br>
Share your stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""
