def pytest_emoji_xfailed(config):
    return "🤷‍♂️ ", "XFAIL 🤷‍♂️ "


pytest_plugins = ("tests.plugins.exceptions_collector",)
