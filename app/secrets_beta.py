import toml
import os
import datetime
import streamlit as st

SECRETS_LOCATION = os.path.join(".", ".streamlit", "secrets.toml")


def _parse():
    secrets = {}
    with open(SECRETS_LOCATION) as f:
        secrets = toml.load(f)
    # Don't handle exceptions for open(), so they show in Streamlit app.
    for k, v in secrets.items():
        _maybe_set_environment_variable(k, v)
    return secrets


def _maybe_set_environment_variable(k, v):
    value_type = type(v)
    if value_type in [str, int, float]:
        os.environ[k] = str(v)


st.secrets = _parse()
