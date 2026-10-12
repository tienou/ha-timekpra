"""Load the integration modules that don't need Home Assistant.

``custom_components/timekpra/__init__.py`` imports Home Assistant. To unit-test
the pure modules (``timekpr_data``, ``ssh``) without installing it, register a
bare package object for the folder: importing ``timekpra_pkg.ssh`` then
resolves ``from .timekpr_data import …`` without running ``__init__.py``.
"""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = REPO_ROOT / "custom_components" / "timekpra"
PKG_NAME = "timekpra_pkg"

# Lets Home Assistant's loader import ``custom_components.timekpra`` in the
# optional integration tests (tests/test_ha_integration.py).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if PKG_NAME not in sys.modules:
    pkg = types.ModuleType(PKG_NAME)
    pkg.__path__ = [str(PKG_DIR)]  # type: ignore[attr-defined]
    sys.modules[PKG_NAME] = pkg


def load(module: str):
    """Import ``custom_components/timekpra/<module>.py`` without HA."""
    return importlib.import_module(f"{PKG_NAME}.{module}")
