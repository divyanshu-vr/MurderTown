# mm.orchestrator: running a game

Owns the order of play: casting, then each Day's Phases, checking for a winner after every Phase.

**May import:** `mm.engine`, `mm.agents`.

**Entry points**
- `game.py`: `play_game(config, brain_for, observers)` plays a whole game and returns its events and final state. `Game.decide` asks one Resident and checks the answer is legal; `Game.decide_all` asks several at once and returns answers in the order asked.
- `log.py`: the append-only `EventLog`. Appending applies the event to the true state, stamps it, then tells each observer (storage, the live bus) in order.
- `phases/`: one module per Phase, plus `reflection.py`, the reflection step that runs after Dawn and after the Vote for every Resident with news. Each builds requests, collects decisions, calls the engine's rules and appends events, naming the decision that caused each one.

**Why it is shaped this way:** Phases stay thin because the rules live in the engine; concurrent answers are appended in seat order so the log is the same however fast each Brain answers.
