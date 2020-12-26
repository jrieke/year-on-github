from streamlit import bootstrap


def test_app_debug():
    """
    For manual debugging via breakpoints.

    Will open browser window with http://localhost:8503/ and stop at the set breakpoint.
    If the breakpoint is in code after the "Show preview" click, needs to be triggered
    by manually clicking "Show preview" just like regular usage.
    """
    script_name = "app/main.py"
    bootstrap.run(script_name, f"run.py {script_name}", [])
