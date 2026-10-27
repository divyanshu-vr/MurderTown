# mm.engine: the rules

Owns everything that decides what is true in a game: the configuration and its bounds, roles and sides, casting, the events and who may perceive each one, the state fold, the Open floor, the Showdown, the Vote and the win conditions.

**May import:** nothing else from `mm`. No I/O, clocks or async, so every rule is a plain function that a test can call directly.

**Entry points**
- `events.py`: every event type, each declaring its own `visibility()`. Start here when adding behaviour.
- `state.py`: `GameState.fold(events)`. The full log gives the truth; one Resident's perceived events give what they know.
- `perception.py`: `perceived_by(events, resident)`, the only way a Resident learns anything, and what a Resident has perceived since their last reflection.
- `decisions.py`: what a Resident can be asked (`DecisionRequest`) and the shape of each answer.
- `rules.py` and `vote.py`: legality of decisions, the word limit on anything a Resident says, the tally, banishment and the verdict.
- `discussion.py`: who speaks next on the Open floor, when the Open floor is over, and which names a Statement records.
- `showdown.py`: whether a Sheriff may still fire, at whom, and the deaths a shot causes.
- `casting.py`: names, seats, personas and roles, all drawn from the game's seeded random source.
- `personas.py`: who each Resident is as a person. The occupation is public; the rest is private.

**Why it is shaped this way:** keeping the rules free of I/O and randomness-from-nowhere makes a game a pure function of its configuration and decisions, which is what makes replay, resume and the isolation tests possible.
