# mm.agents: decision sources

Owns the things that play a Resident. Every one of them answers a `DecisionRequest`, seeing only the events that Resident may perceive.

**May import:** `mm.engine`.

**Entry points**
- `brain.py`: the `Brain` interface (`decide(request, view)`) and `BrainFactory`, which gives each Resident its own Brain.
- `scripted.py`: `ScriptedBot` and `scripted_bots(seed)`, rule-based Residents that play legally without a language model. Town bots vote at random; Murderer bots never vote for a teammate.

**Why it is shaped this way:** the game runner never knows what kind of Brain it is talking to, so scripted bots, LLM Agents and, later, a human seat are interchangeable per Resident.
