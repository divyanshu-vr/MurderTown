# mm.agents: decision sources

Owns the things that play a Resident. Every one of them answers a `DecisionRequest`, seeing only the events that Resident may perceive.

**May import:** `mm.llm`, `mm.observability`, `mm.engine`.

**Entry points**
- `brain.py`: the `Brain` interface (`decide(request, view)` returns an `Answer`, or raises `ModelFailureError` when the model gave no answer at all) and `BrainFactory`, which gives each Resident its own Brain.
- `scripted.py`: `ScriptedBot` and `scripted_bots(seed)`, rule-based Residents that play legally without a language model. They suspect whoever they accused (a Detective, whoever its Findings named), Murderer bots lie (claiming to be Civilians, speaking up for a teammate), and now and then a bot lapses into a fallback, so recorded games show lies, swings in suspicion and fallbacks, without drawing more from a bot's Random than playing does.
- `llm_brain.py`: `LLMBrain`. Every decision kind runs the same pipeline: build the prompt, call the model, read the answer, retry once with the problem quoted, fall back to a safe default, and record every attempt, scrubbed, before returning. A timeout or an error (or a provider that raises) fails the decision instead, which aborts the game. A resumed game's Agents are given its recorded calls (`recorded`): an attempt already recorded is answered from its record (`ModelCall.as_reply`), so no call is made twice. Each call's cost comes from the price table, and a model with no price is refused before the game starts.
- `prompting.py` and `prompts/`: the prompt, built only from perceived events and ordered from most to least stable (system briefing, memory, task). A role's Night knowledge (protections, Findings) sits in the memory block. The narrator's recap gets its own short prompt: the facts and the public events since the previous Dawn. The templates are versioned text files; `prompt_version()` hashes them.
- `memory.py`: an Agent's notebook, journal and dossier, folded from its own reflection events (there is no separate memory store), and `mind_of`, one Resident's mind at a moment, for the Mind inspector's endpoint.
- `answers.py`: the shape of a usable answer per decision kind, its safe default, and `scrubbed`, which keeps email addresses and file paths out of the game and out of call records.
- `lineup.py`: `lineup_brains(config, providers, record, recorded)` and `llm_agents(...)` (every Resident on one provider and model), every Resident's Brain as the game's lineup says: a scripted bot, or an Agent on the provider and model it names. A lineup that cannot be played is refused before the game starts.
- `cassette.py`: `Cassette`, a provider that answers a replayed game from its recorded model calls, each answering only the very same request (`request_hash`).
- `calls.py`: `ModelCall`, the record of one model attempt; `label_generation`, which labels the attempt's span as a Langfuse generation (each record keeps its trace id); and `Cost`, what some calls used and cost together, which the cost meter and `mm play`'s summary show.

**Why it is shaped this way:** the game runner never knows what kind of Brain it is talking to, so scripted bots, LLM Agents and, later, a human seat are interchangeable per Resident. One pipeline for every decision kind means adding a decision is a table entry and a template, not a new copy of the flow.
