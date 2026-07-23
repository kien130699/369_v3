__all__ = ["__version__"]
__version__ = "0.2.1"

# Install causal execution guards before app.main or tests use BotRuntime.
from .signal_fill_guard import install_signal_fill_guard

install_signal_fill_guard()
