from typing import Union, Dict
import re
import urllib

import github_reader


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
⭐ New stars: {new_stars}<br>
🔥 Hottest: {hottest_repo} (+{hottest_new_stars} ⭐)
<br><br>
Share your own stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""

ORG_TEMPLATE = """
<p id="tweet">
Our year on Github 2020 🧑‍💻✨ {username}
<br><br>
⭐ New stars: {new_stars}<br>
🔥 Hottest: {hottest_repo} (+{hottest_new_stars} ⭐)
<br><br>
Share your own stats: <a href="https://gh2020.jrieke.com">gh2020.jrieke.com</a> | Built by <a href="https://twitter.com/jrieke">@jrieke</a> w/ <a href="https://twitter.com/streamlit">@streamlit</a> <a href="https://twitter.com/github">@github</a> | <a href="https://twitter.com/search?q=%23github2020">#github2020</a>
</p>
"""


def fineprint(runtime: Union[float, None] = None):
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


def tweet(stats: Dict) -> str:
    """Generate tweet html text based on `stats`."""
    if stats["is_org"]:
        tweet_html = ORG_TEMPLATE.format(**stats)
    else:
        tweet_html = USER_TEMPLATE.format(**stats)
    return tweet_html


def tweet_button(tweet_html: str) -> str:
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
# Code for copy button in mains ccript:
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
