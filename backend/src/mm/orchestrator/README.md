# mm.orchestrator: running a game

Owns the order of play: casting, then each Day's Phases, checking for a winner after every Phase.

**May import:** `mm.engine`, `mm.agents`.

**Entry points**
- `game.py`: `play_game(config, brain_for, observers, clock)` plays a whole game and returns its events and final state. The clock only times the Open floor; tests pass a fake one. `Game.decide` asks one Resident and checks the answer is legal; `Game.decide_all` asks several at once and returns answers in the order asked; it stamps every decision id before any answer can arrive, so ids never depend on timing. `Game.decided` says whether a side has already won; a Phase checks it after any death, so nobody acts once the game is over. Every decision causes at least one event, appended with `cause=` so it names the decision; a Sheriff holding fire, for instance, causes a `SheriffHeldFire` that only Spectators perceive. A fallback is reported once, beside the first event its decision caused.
- `log.py`: the append-only `EventLog`. Appending applies the event to the true state, stamps it, then tells each observer (storage, the live bus) in order. `unlogged` stamps something already heard but not appended yet.
- `phases/`: one module per Phase. Each builds requests, collects decisions, calls the engine's rules and appends events, naming the decision that caused each one. Dawn and the Vote end with `reflection.reflect`, in which every living Resident with news writes a reflection. The Sheriff's choice is one function, `showdown.sheriff_decides`, which the Showdown or Night calls depending on the configuration. Night runs the Den one Murderer at a time, then asks for every kill vote, protection and investigation at once; Dawn announces the result, then the narrator recaps. Dusk runs its Conversations in waves: each round asks the next speaker of every unfinished Conversation at once, and a wave's messages are held back (`decide_all(..., pending)` lets the speakers hear them) and appended Conversation by Conversation when the wave ends.
- `narrator.py`: `NARRATOR`, the storyteller. It borrows a Resident record only so every decision source can give it a Brain, and perceives only public events.

**Why it is shaped this way:** Phases stay thin because the rules live in the engine; concurrent answers are appended in a fixed order (seat order; at Night by role; at Dusk, each wave's messages Conversation by Conversation) so the log is the same however fast each Brain answers.
