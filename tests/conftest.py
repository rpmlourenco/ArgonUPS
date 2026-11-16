"""Permit protocol/client unit tests on PCs without Home Assistant installed."""

import importlib.util
import sys
import types
from pathlib import Path

# Only bypass package startup when HA is absent. HA integration tests use the
# actual package and pytest-homeassistant-custom-component on Linux.
if importlib.util.find_spec("homeassistant") is None:
    package = types.ModuleType("custom_components.argon_ups")
    package.__path__ = [
        str(Path(__file__).resolve().parents[1] / "custom_components" / "argon_ups")
    ]
    sys.modules[package.__name__] = package
