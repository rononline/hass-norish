"""Test setup: import the integration from the repo, stub missing heavy deps.

Some Home Assistant components import optional native libraries (e.g.
``turbojpeg`` for camera, ``habluetooth`` via the frontend chain). Only the
ones that are not installed are replaced by empty modules.
"""
import importlib
import importlib.abc
import importlib.machinery
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPTIONAL_NATIVE = (
    "turbojpeg", "habluetooth", "bleak", "bleak_retry_connector",
    "bluetooth_adapters", "bluetooth_auto_recovery", "bluetooth_data_tools",
    "dbus_fast", "pyric", "av", "go2rtc_client", "hass_nabucasa",
)


def _missing(name: str) -> bool:
    try:
        importlib.import_module(name)
    except Exception:  # noqa: BLE001 – not installed or broken: stub it
        return True
    return False


STUBBED = {name for name in OPTIONAL_NATIVE if _missing(name)}


class _StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        module = MagicMock(name=spec.name)
        module.__path__ = []
        module.__spec__ = spec
        module.__name__ = spec.name
        return module

    def exec_module(self, module):
        pass


class _StubFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in STUBBED:
            return importlib.machinery.ModuleSpec(name, _StubLoader(), is_package=True)
        return None


sys.meta_path.insert(0, _StubFinder())
