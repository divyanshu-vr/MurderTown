"""The narrator: the game's storyteller, who recaps each Day at Dawn.

The narrator is not a Resident of the town but decides like one. It borrows a
Resident record only so that every decision source (scripted bots, test
puppets, Agents) can give it a Brain. Its name is in no visibility list, so it
perceives only what the whole town perceives.
"""

from mm.engine import Resident

NARRATOR = Resident(name="Narrator", seat=-1, occupation="narrator")
