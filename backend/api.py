"""
Compatibility shim for the deprecated legacy API module.

The active runtime entrypoint is ``main.py``.
This module re-exports the old API from ``backend/legacy/api.py`` so older
local commands such as ``uvicorn api:app`` keep working.
"""

from legacy.api import *  # noqa: F401,F403
