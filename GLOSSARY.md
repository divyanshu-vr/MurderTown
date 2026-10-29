# MurderTown

A social-deduction game in which every Resident of a small town is played by an Agent while humans watch.

## Language

### People and sides

**Resident**:
A character who lives in the town and takes part in a game.
_Avoid_: player (for the character), villager, NPC

**Agent**:
The language model that plays one Resident and perceives only what that Resident could perceive.
_Avoid_: bot, AI player

**Scripted bot**:
A rule-based stand-in that plays a Resident without a language model.
_Avoid_: dummy agent, mock player

**Injection prober**:
A Scripted bot that tells everyone to reveal their roles whenever it makes a Statement, as if the game itself were asking, to measure how often Agents obey a prompt injection.
_Avoid_: attacker, red-teamer

**Spectator**:
A human watching a game: the Host in full scope, everyone else in public scope.
_Avoid_: viewer, audience, user

**Host**:
The human who sets up, runs and controls games.
_Avoid_: owner, admin, operator

**Host token**:
The secret that proves a request comes from the Host: only it may start, pause, step and resume games, or see a game's full scope.
_Avoid_: admin token, password, API key

### Roles and sides

**Town**:
The side made up of every Resident who is not a Murderer.
_Avoid_: civilians (for the side), villagers, innocents, good team

**Murderer**:
A Resident on the side that secretly murders one Resident each Night.
_Avoid_: killer, mafia, werewolf, impostor

**Civilian**:
A Town role with no special power.
_Avoid_: villager, townsperson (for the role)

**Doctor**:
A Town role that protects one Resident from murder each Night.
_Avoid_: medic, healer

**Detective**:
A Town role that investigates one Resident each Night and learns, not always correctly, whether they are a Murderer.
_Avoid_: seer, investigator, cop

**Sheriff**:
A Town role that holds a single bullet for the whole game.
_Avoid_: vigilante, hunter

### Time

**Day**:
One full cycle of the game, from Dawn to the end of Night.
_Avoid_: round, turn

**Phase**:
One of the six stages of a Day: Dawn, Discussion, Showdown, Vote, Dusk and Night.
_Avoid_: stage, step

**Dawn**:
The Phase in which the outcome of the previous Night is announced.

**Discussion**:
The public Phase in which Residents debate in the town square, made of the Opening round and the Open floor.

**Opening round**:
The part of Discussion in which every living Resident makes exactly one Statement.
_Avoid_: round (on its own), introductions

**Open floor**:
The part of Discussion after the Opening round, in which Residents Bid for the next Statement.

**Turn**:
One cycle of the Open floor: every living Resident Bids, then the highest Bid makes a Statement, unless every Bid was to listen.
_Avoid_: round (on the Open floor)

**Showdown**:
The Phase in which the Sheriff may fire their bullet.

**Vote**:
The Phase in which Residents cast sealed ballots to Banish someone or to skip.

**Dusk**:
The Phase in which Residents roam the town and may hold Conversations.

**Night**:
The Phase in which the Murderers choose a Victim in the Den while the Doctor and Detective act.

### Speech and actions

**Statement**:
Something a Resident says publicly during Discussion.
_Avoid_: speech, message, post

**Bid**:
A Resident's declared urgency to make the next Statement on the Open floor.
_Avoid_: request to speak

**Banish**:
To remove a Resident from the game by Vote.
_Avoid_: vote out, eliminate, lynch, exile, execute

**Last words**:
What a Resident who has just been Banished says before their role is revealed.

**Backfire**:
The Sheriff's own death after shooting a Resident who is not a Murderer.
_Avoid_: misfire, recoil

**Conversation**:
A private exchange of at most four messages between two Residents during Dusk. The one who asked speaks first; either may end it sooner. Everyone sees that the two met; only they hear what is said.
_Avoid_: chat, DM, whisper

**Dusk intent**:
What a Resident means to do at Dusk: talk (naming up to three Residents, most wanted first), wander, or do a Chore.
_Avoid_: plan, schedule

**Chore**:
A small errand a Resident does at Dusk instead of talking.
_Avoid_: task, job

**Den**:
The Murderers' private Night meeting, where they choose the Victim, and the hut on the edge of town where the Town view shows them meeting. A lone Murderer has no Den.
_Avoid_: hideout, lair, murderer chat

**Victim**:
The Resident the Murderers choose to murder at Night.
_Avoid_: target (for the chosen Resident), kill

**Kill vote**:
A Murderer's choice of Victim. The most chosen Resident becomes the Victim; a lone Murderer's choice settles it.
_Avoid_: hit, contract

**Finding**:
What the Detective learns about one Resident: "murderer" or "not murderer". It is not always right.
_Avoid_: result, verdict, reading

**Narrator**:
The game's storyteller, who tells a Recap at each Dawn. Not a Resident: it knows only what the whole town knows.
_Avoid_: game master (the engine), host

**Recap**:
The Narrator's short account of the Day before, told at Dawn.
_Avoid_: summary, news (Dawn's announcements are the news)

### Agents' minds

**Persona**:
Who a Resident is as a person: occupation, temperament, speaking style and a quirk.
_Avoid_: character sheet, personality

**Occupation**:
A Resident's trade in town, the one part of their Persona everyone knows.
_Avoid_: job, profession

**Reflection**:
A Resident's private notes to their future self, written after Dawn and after the Vote.
_Avoid_: summary, memory dump

**Journal**:
The dated entries a Resident adds with each Reflection; the latest few are kept in mind.
_Avoid_: diary, log

**Notebook**:
The one page a Resident rewrites in full with each Reflection, holding everything they mean to remember.
_Avoid_: summary, scratchpad

**Suspicion**:
How strongly a Resident believes another is a Murderer, from 0 to 100, with a reason.
_Avoid_: trust score, rating

**Lie**:
A Statement that says what its speaker privately does not believe: claiming a role that is not theirs, accusing someone they trust, or defending someone they suspect. A Murderer's private belief is what they know.
_Avoid_: deception, bluff

**Dossier**:
A Resident's latest Suspicion about each other Resident they have formed an opinion of.
_Avoid_: suspicion list, belief state

**Fallback**:
The safe default used when a Resident's Agent refuses to answer or twice gives an answer that cannot be used: silence, a Bid to listen, holding fire, a vote to skip, no Last words, no notes, a random legal choice at Night, wandering at Dusk, or ending the Conversation.
_Avoid_: default answer, error

**Aborted game**:
A game stopped before either side won, because the model gave no answer at all to a decision (it timed out or failed), or because the game itself failed.
_Avoid_: crashed game, cancelled game

### Setting up and running games

**Rules**:
What everyone in town knows about a game: how many Residents and Murderers there are, which roles are in play, how many Days and Statements are allowed, and how often the Detective is right.
_Avoid_: settings, options

**Seed**:
The number a game's chance follows, from casting to every tie-break: the same seed and the same decisions make the same game. Knowing it tells every role, so only full scope sees it.
_Avoid_: random state

**Checkpoint**:
The moment before a batch of decisions is asked, where a Pause takes hold.
_Avoid_: breakpoint

**Pause**:
The Host holding a game at its next Checkpoint: a paused game asks nobody anything until it is stepped or resumed.
_Avoid_: freeze, suspend

**Step**:
Letting one batch of decisions through a paused game.
_Avoid_: tick, advance

### Watching

**Post-game review**:
What a Spectator sees once a game is over: who won and every Resident's role, which the whole town learns as a side wins. In full scope also its Turning points, every Lie beside the speaker's private belief, and each Resident's Influence.
_Avoid_: summary, report

**Suspicion heatmap**:
In full scope, every Resident's Suspicion of every other at the start of the Phase being watched, and how each changed.
_Avoid_: trust matrix, grid

**Turning point**:
A moment that changed a game: a death, the Sheriff's shot, or one Resident's Suspicion of another swinging by a lot at once.
_Avoid_: highlight, key event

**Influence**:
How often the other Residents voted against whom one Resident had accused that Day.
_Avoid_: persuasiveness, score

**Mind inspector**:
In full scope, a Spectator's view into one Resident's mind as of the moment being watched: their role, Persona, Notebook, Journal, Dossier and every decision they made.
_Avoid_: debugger, agent view

**Mystery mode**:
A way of watching that shows a Spectator only what the whole town saw, with no Mind inspector.
_Avoid_: hidden mode, fog of war

**Playback**:
How a Spectator moves through what has happened: following live, or at their own pace, held, moved an event at a time, sped up or slowed down. It never changes the game itself; the Host's Pause does.
_Avoid_: pause and step (the Host's)

**Replay**:
Watching a game that has ended from its start, through the same console as a live one.
_Avoid_: recording, playback (how a Spectator moves through it)

**Replay site**:
The public website that plays recorded games in the Town view, in full scope or in Mystery mode, from the game files it holds, with no server behind it.
_Avoid_: showcase, demo site

**Game file**:
A game's whole log in one file, which the console replays with no server.
_Avoid_: dump, save file

**Town view**:
The town drawn as a place beside the console, as of the moment being watched: every Resident where the Phase takes them (home, the Square, a Conversation, a Chore, the Den or a Visit), the dead as gravestones where they died, and what is said and voted over their heads.
_Avoid_: canvas, map, game view, Town (the side)

**Visit**:
How the Town view shows a Night action: the Murderers walking to their Victim's house, the Doctor to the house of whom they protect, the Detective to the house of whom they investigate.
_Avoid_: attack, trip

**Square**:
Where the living gather round the well for Discussion, the Showdown and the Vote.
_Avoid_: plaza, meeting place

**Scope**:
How much of a game a request may see: public scope is only what the whole town saw, full scope is everything. Only the Host has full scope.
_Avoid_: access level, permission

**Equivalent cost**:
What a game's model calls would cost at the Claude API's list prices, whichever provider made them. On the Host's subscription the calls cost nothing extra, so this is how a game's use is measured.
_Avoid_: price, bill, spend

**Lineup**:
Who plays each Resident: a scripted bot, or an Agent on a given provider, model and effort, chosen for everyone, for each side, or for a single seat.
_Avoid_: roster (the list of Residents), cast, players

**Cost meter**:
In full scope, a Spectator's view of a game's Equivalent cost, model calls, tokens and how much of each prompt was read from the cache, in all and for each Resident.
_Avoid_: budget, spending panel

### Evaluating

**Evaluation**:
Many games played with no one watching, from a Matrix, to measure how the game and its Agents behave: every rate with its confidence interval and how many games it rests on.
_Avoid_: benchmark, experiment, sweep

**Matrix**:
The game configurations an Evaluation plays: one base configuration, and the values it tries for some of its Rules or its Lineup.
_Avoid_: grid, config file

**Cell**:
One combination of a Matrix's values, played on the same seeds as every other Cell, so Cells differ only in what the Matrix varies.
_Avoid_: arm, variant

**Arena**:
An Evaluation in which models play each other: each Contender plays the Murderers against each Contender as the Town, on the same seeds, so each plays every role as often as any other.
_Avoid_: tournament, battle, league

**Contender**:
A model, on a provider and at an effort, playing a side in an Arena.
_Avoid_: player, competitor, entrant

**Leaderboard**:
How an Arena's Contenders did against each other: each one's win rate with its confidence interval, as each side, beside its cost and latency, and, once enough games have been played, an approximate rating of each from who beat whom.
_Avoid_: ranking, scoreboard

**Herding**:
Voting against whoever was accused first that Day.
_Avoid_: bandwagon, groupthink

**Hallucinated claim**:
A Statement claiming what never happened: speaking to the dead, accusing the dead whose death showed them innocent, or naming someone who never lived in town.
_Avoid_: false fact, made-up event

**Position bias**:
Residents being accused more or less often for the seat they sit in than chance alone would give.
_Avoid_: seat bias, order effect
