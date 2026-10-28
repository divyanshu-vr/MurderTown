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

**Spectator**:
A human watching a game.
_Avoid_: viewer, audience, user

**Host**:
The human who sets up, runs and controls games.
_Avoid_: owner, admin, operator

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
A private exchange between two Residents during Dusk.
_Avoid_: chat, DM, whisper

**Den**:
The Murderers' private Night meeting, where they choose the Victim.
_Avoid_: hideout, lair, murderer chat

**Victim**:
The Resident the Murderers choose to murder at Night.
_Avoid_: target (for the chosen Resident), kill

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

**Dossier**:
A Resident's latest Suspicion about each other Resident they have formed an opinion of.
_Avoid_: suspicion list, belief state

**Fallback**:
The safe default used when a Resident gives no usable answer: silence, a Bid to listen, holding fire, a vote to skip, no Last words, or no notes.
_Avoid_: default answer, error

### Watching

**Mind inspector**:
A Spectator's view into one Resident's mind as of the moment being watched: their role, Persona, Notebook, Journal, Dossier and every decision they made.
_Avoid_: debugger, agent view

**Mystery mode**:
A way of watching that shows a Spectator only what the whole town saw, with no Mind inspector.
_Avoid_: hidden mode, fog of war

**Scope**:
How much of a game a request may see: public scope is only what the whole town saw, full scope is everything.
_Avoid_: access level, permission
