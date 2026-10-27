"""The HTTP and WebSocket API that Spectators and the Host talk to."""

from mm.api.app import create_app
from mm.api.settings import Settings

__all__ = ["Settings", "create_app"]
