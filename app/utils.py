import streamlit as st


def local_css(file_name):
    """Loads a local .css file into streamlit."""
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def remote_css(url):
    """Loads a remote .css file into streamlit."""
    st.markdown(f'<link href="{url}" rel="stylesheet">', unsafe_allow_html=True)


def material_icon(icon_name):
    """
    Shows a material icon in streamlit.
    
    To use this, call at the beginning of your script: 
    remote_css("https://fonts.googleapis.com/icon?family=Material+Icons")
    """
    st.markdown(f'<i class="material-icons">{icon_name}</i>', unsafe_allow_html=True)
