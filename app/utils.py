import datetime

import streamlit as st


def icon(emoji: str):
    """Shows an emoji as a Notion-style page icon."""
    st.write("")
    st.write(
        f'<span style="font-size: 78px; line-height: 1">{emoji}</span>',
        unsafe_allow_html=True,
    )


def format_timedelta(delta: datetime.timedelta) -> str:
    """Formats timedelta to x days, x h, x min, x s."""
    s = delta.total_seconds()
    days, remainder = divmod(s, 86400)
    hours, remainder = divmod(s, 3600)
    mins, secs = divmod(remainder, 60)

    days = int(days)
    hours = int(hours)
    mins = int(mins)
    secs = int(secs)

    output = f"{secs} s"
    if mins:
        output = f"{mins} min, " + output
    if hours:
        output = f"{hours} h, " + output
    if days:
        output = f"{days} days, " + output
    return output


def local_css(file_name: str) -> None:
    """Loads a local .css file into streamlit."""
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def remote_css(url: str) -> None:
    """Loads a remote .css file into streamlit."""
    st.markdown(f'<link href="{url}" rel="stylesheet">', unsafe_allow_html=True)


def material_icon(icon_name: str) -> None:
    """
    Shows a material icon in streamlit.

    To use this, call at the beginning of your script:
    remote_css("https://fonts.googleapis.com/icon?family=Material+Icons")
    """
    st.markdown(f'<i class="material-icons">{icon_name}</i>', unsafe_allow_html=True)
