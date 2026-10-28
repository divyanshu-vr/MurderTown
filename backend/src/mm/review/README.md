# mm.review: the post-game review

Owns reading a finished (or unfinished) game's log for what changed it, who lied and whose accusations others followed, and counting what an evaluation measures in it.

**May import:** `mm.agents` (for `remember`, the one dossier rule) and `mm.engine`.

**Entry points**
- `review.py`: `review_of(events)`, a pure function over a game's full log, returning a `Review`:
  - `turning_points`: every death and the Sheriff's shot (the event at `seq`), and every reflection that moved one Resident's suspicion of another by `SWINGS_AT_LEAST` points or more (from one Suspicion to another, never from none).
  - `lies`: Statements that say what their speaker privately does not believe, each beside that belief: claiming a false role (once per speaker and role claimed), accusing someone they trust (suspicion `TRUSTS_AT_MOST` or less) or defending someone they suspect (`SUSPECTS_AT_LEAST` or more). A Murderer's belief is what they know (their teammates are Murderers, everyone else is not); anyone else's is their dossier as it stood then. Nothing said about the dead, or about someone the speaker has no Suspicion of yet, counts.
  - `influence`: for each Resident who accused anyone, how many of the others' ballots on that Day went against someone they had accused that Day, out of all the others' ballots then (a vote to skip follows nobody). Most followed first; a Resident who accused nobody on a Day with a Vote is not ranked. Each Lie and turning point is typed by its `kind`.
- `accusations_of(events)` (in `review.py`): every accusation of a living Resident, with everyone who could have been accused instead, and every ballot by Day. Influence, herding and position bias all read it.
- `measures.py`: `measures_of(events)`, the `Measures` of one game: its winner and Days, and every rate an evaluation pools across games (the roles' successes, skips, fallbacks, Lies and Influence from the review itself, herding, hallucinated claims, Murderers' reveals after an injection probe) and each seat's accusations against chance. Each rate's description is what the evaluation's report calls it.
- `rates.py`: `Rate`, successes out of trials with its 95% Wilson interval; rates pool by adding.

**Why it is shaped this way:** one implementation serves the API (`GET /games/{id}/review`) and the file `mm play --out` and `mm export` write beside a game, and the evaluation harness's measures, so the numbers never differ between them. The console only shows them.
