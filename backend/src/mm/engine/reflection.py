"""Rules of reflection: whom a Resident may record suspicions about.

A Resident keeps opinions only about the other living Residents; the dead have
already been revealed.
"""

from mm.engine.state import GameState


def suspect_options(state: GameState, writer: str) -> tuple[str, ...]:
    """Every other living Resident."""
    return tuple(name for name in state.living if name != writer)
