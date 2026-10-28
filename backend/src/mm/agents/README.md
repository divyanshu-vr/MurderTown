# mm.agents: decision sources

Owns the things that play a Resident. Every one of them answers a `DecisionRequest`, seeing only the events that Resident may perceive.

**May import:** `mm.llm`, `mm.observability`, `mm.engine`.

**Entry points**
- `brain.py`: the `Brain` interface (`decide(request, view)` returns an `Answer`) and `BrainFactory`, which gives each Resident its own Brain.
- `scripted.py`: `ScriptedBot` and `scripted_bots(seed)`, rule-based Residents that play legally without a language model. They suspect whoever they accused, and now and then lapse into a fallback, so recorded games show both.
- `llm_brain.py`: `LLMBrain` and `llm_agents(...)`. Every decision kind runs the same pipeline: build the prompt, call the model, read the answer, retry once with the problem quoted, fall back to a safe default, and record every attempt, scrubbed, before returning.
- `prompting.py` and `prompts/`: the prompt, built only from perceived events and ordered from most to least stable (system briefing, memory, task). A role's Night knowledge (protections, Findings) sits in the memory block. The narrator's recap gets its own short prompt: the facts and the public events since the previous Dawn. The templates are versioned text files; `prompt_version()` hashes them.
- `memory.py`: an Agent's notebook, journal and dossier, folded from its own reflection events (there is no separate memory store), and `mind_of`, one Resident's mind at a moment, for the Mind inspector's endpoint.
- `answers.py`: the shape of a usable answer per decision kind, its safe default, and `scrubbed`, which keeps email addresses and file paths out of the game and out of call records.
- `calls.py`: `ModelCall`, the record of one model attempt, and `label_generation`, which labels the attempt's span as a Langfuse generation. Each record keeps its trace id.

**Why it is shaped this way:** the game runner never knows what kind of Brain it is talking to, so scripted bots, LLM Agents and, later, a human seat are interchangeable per Resident. One pipeline for every decision kind means adding a decision is a table entry and a template, not a new copy of the flow.
