"""Shared state module to avoid circular import issues."""

from typing import Dict, Optional
from fastapi import WebSocket

# Store WebSocket connections - shared across all modules
sketchpad_connections: Dict[str, WebSocket] = {}

# Store the latest Chainlit session ID (for single-user mode)
latest_chainlit_session: Optional[str] = None


def set_latest_chainlit_session(session_id: str):
    """Set the latest Chainlit session ID."""
    global latest_chainlit_session
    latest_chainlit_session = session_id
    print(f"[STATE] Set latest Chainlit session: {session_id}")


def get_latest_chainlit_session() -> Optional[str]:
    """Get the latest Chainlit session ID."""
    return latest_chainlit_session


def add_sketchpad_connection(key: str, websocket: WebSocket):
    """Add a sketchpad WebSocket connection."""
    sketchpad_connections[key] = websocket
    print(f"[STATE] Added sketchpad connection: {key}, total={list(sketchpad_connections.keys())}")


def remove_sketchpad_connection(key: str):
    """Remove a sketchpad WebSocket connection."""
    if key in sketchpad_connections:
        del sketchpad_connections[key]
        print(f"[STATE] Removed sketchpad connection: {key}")


def get_sketchpad_connection(key: str) -> Optional[WebSocket]:
    """Get a sketchpad WebSocket connection."""
    return sketchpad_connections.get(key)


def get_all_sketchpad_connections() -> Dict[str, WebSocket]:
    """Get all sketchpad WebSocket connections."""
    return sketchpad_connections

