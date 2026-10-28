# mm.engine: the rules

Owns everything that decides what is true in a game: the configuration and its bounds, roles and sides, casting, the events and who may perceive each one, the state fold, the Open floor, the Showdown, the Vote, Dusk, the Night and the win conditions.

**May import:** nothing else from `mm`. No I/O, clocks or async, so every rule is a plain function that a test can call directly.

**Entry points**
- `events.py`: every event type, each declaring its own `visibility()`. Start here when adding behaviour.
- `state.py`: `GameState.fold(events)`. The full log gives the truth; one Resident's perceived events give what they know.
- `perception.py`: `perceived_by(events, resident)`, the only way a Resident learns anything, and what a Resident has perceived since their last reflection.
- `decisions.py`: what a Resident can be asked (`DecisionRequest`) and the shape of each answer.
- `rules.py` and `vote.py`: legality of decisions, the word limit on anything a Resident says, filtering the names a Resident gives, the tally, banishment and the verdict.
- `discussion.py`: who speaks next on the Open floor, and when the Open floor is over.
- `showdown.py`: whether a Sheriff may still fire, at whom, and the deaths a shot causes.
- `night.py`: whom the Murderers may kill, the Doctor protect and the Detective investigate, how often a Finding is right, and what Dawn announces.
- `dusk.py`: who talks to whom at Dusk, in which wave, and who speaks next in a Conversation, with every limit.
- `tally.py`: the top choice with a tie drawn by the game's seed, shared by the Open floor and the kill vote.
- `casting.py`: names, seats, personas and roles, all drawn from the game's seeded random source; `seated_roles(config)` tells the role at each seat before the game starts.
- `config.py`: `GameConfig`, everything the Host chooses, with its bounds: the `Rules` everyone in town knows, plus the seed and the `Lineup` of who plays each Resident (`PlayedBy`: a provider, a model and an `Effort`). Casting follows from the seed, so no Resident may know it and only full scope shows it: a game's log opens with `GameConfigured`, which no Resident perceives, then `GameStarted`, which carries only the rules.
- `personas.py`: who each Resident is as a person. The occupation is public; the rest is private.

**Why it is shaped this way:** keeping the rules free of I/O and randomness-from-nowhere makes a game a pure function of its configuration and decisions, which is what makes replay, resume and the isolation tests possible.
