# Recipes

Step-by-step guides for the changes this codebase is built to absorb. Each recipe is done when its tests pass and the regenerated files are committed.

## Regenerate the shared contract

Run after any change to an event, a decision answer or an API model:

```
cd backend
uv run mm schema
uv run mm play --seed 147 --quiet --out ../fixtures/scripted-game.ndjson
uv run mm minds
cd ../frontend
pnpm gen:types
```

## Add an event type

1. Define the payload in `backend/src/mm/engine/events.py`: a `type` literal and a `visibility()` saying who may perceive it. Add it to the `EventPayload` union.
2. If it changes state, handle it in `GameState.apply` (`engine/state.py`). If it only records something, leave the fold alone.
3. Append it from the Phase that causes it (`orchestrator/phases/`), through `game.append`. If whether it happens depends on anything but the seed and the decisions (the clock, say), the event itself must be the record: a resumed game replays from the seed and reads such moments from its stored log, as `Game.open_floor_out_of_time` does for `OpenFloorTimedOut`.
4. Decide how Agents read it: a line in `_line` or a fact in `_facts` (`agents/prompting.py`). `_line`, `GameState.apply` and the transcript's `describe` end in `assert_never`, so `mypy` fails until the new type has a case in each.
5. Regenerate the shared contract. TypeScript's exhaustive `switch` statements then fail to compile at every place that needs a case: the feed line (`ui/describeEvent.ts`), the view fold (`core/gameView.ts`), `decider` and `named` (`core/involved.ts`), the Resident whose decision the event records and those it names, which kind of line it is in the feed's filters (`isSystemLine`, `core/feedFilter.ts`), and how long playback shows it (`core/presentation.ts`; a moment the town should watch play out also goes in `BLOCKING`). Add the transcript line in `cli/transcript.py`.
6. Write a seam-1 test for when the event is appended and who perceives it, and a seam-3 test if Spectators see it.

## Add a decision kind

1. Add the kind to `DecisionKind` and its answer, a `Decision` subclass, in `engine/decisions.py`.
2. Add its legality rule to `why_illegal` (`engine/rules.py`). Its options builder lives with the rules of its Phase, as `ballot_options` lives in `engine/vote.py`.
3. Teach `ScriptedBot` to answer it legally (`agents/scripted.py`).
4. Give LLM Agents what they need: an `AnswerSpec` with its safe default in `ANSWERS` (`agents/answers.py`), either `always(...)` one decision or a function of the request such as `any_option`, and an instructions template in `agents/prompts/decisions/`, listed in `DECISION_TEMPLATES` (`agents/prompting.py`). Say who is asked it, in `ASKED_OF_EVERYONE` or a role's `ASKED_OF_THE_ROLE` (`agents/prompting.py`), so their briefing lists its answer format: on the subscription that is the only place a model learns it (`test_every_kind_of_decision_is_someones_to_answer` fails until you do). If the answer picks a Resident from a list, reuse the `Target` shape and its legality rule.
5. Ask for it from the Phase with `game.decide` (one Resident) or `game.decide_all` (several at once, answers in the order asked), and append the event it causes with `cause=` so the event names the decision. Every decision causes at least one event, even one that changes nothing (a Sheriff holding fire causes `SheriffHeldFire`), so the Mind inspector can list and explain it. The event's payload names the Resident who decided. Do not ask a Resident whose options are empty.
6. Add its label to `decisionLabel` (`frontend/src/ui/labels.ts`); the `Record` type will not compile until you do.
7. Write seam-1 tests that script the answers with a `Puppet`-style test decision source, and seam-2 tests with `FakeModel` for its fallback.

## Add a role

1. Add it to `Role` (`engine/roles.py`). Its side follows from `Role.side`.
2. Add a toggle to `Rules` and include it in `role_deck` (`engine/config.py`), and offer it among the setup form's role toggles (`frontend/src/ui/SetupForm.tsx`).
3. Its powers are decision kinds (see above), asked for by the Phase where they act, and listed for the role in `ASKED_OF_THE_ROLE` (`agents/prompting.py`), so its briefing shows how to answer them.
4. Add its label to `roleLabel` (`frontend/src/ui/labels.ts`). The `Record` type will not compile until you do.

## Change what the review finds

The post-game review is computed once, in `backend/src/mm/review/review.py`; the API, the files written beside a game and the evaluation harness use it, and the console only shows it. Change a rule there with a test on a hand-made log (`tests/test_review.py`), then regenerate the shared contract: the recorded game's review (`fixtures/scripted-game.review.json`) is rewritten with it, and `test_recorded_fixture.py` checks it still holds every kind of lie and turning point the console's tests show.

## Add a measure to the evaluation

1. Add a `Rate` field to `Measures` (`backend/src/mm/review/measures.py`) whose description is what the report calls it, and count it in `measures_of` from the game's log, with a test on a hand-made log (`tests/test_measures.py`). The report lists every rate field with its interval and sample sizes, and pools it across games, with no change.
2. Count anything the post-game review already decides (a Lie, an accusation) from the review's own code, so the two never disagree.
3. A measure that is a measurement rather than a rate (tokens, seconds) goes in the report's measurements (`backend/src/mm/cli/report.py`).

## Add a panel

1. Derive what it shows in `frontend/src/core` (pure, from events), not inside the component.
2. Render it from a component in `frontend/src/ui` and mount it in `GameConsole`.
3. Write a seam-3 test: render from the recorded fixture and assert what a Spectator sees, by role and accessible name.

Panels read what playback has reached (the `events` up to `playback.shown`), not everything received, and what tells private beliefs (the suspicion heatmap, the server's post-game review) is left out of mystery mode. The post-game review's own panel stays, telling only who won and who everyone was.

A panel that shows what the events do not hold gets it from the server, only on the Host's page, since only the Host may ask. Two ways, by how often it changes: the cost meter, asked again as events arrive, takes a source function from `frontend/src/net` (`costSource`, like `explainer`), and its seam-3 test passes a stub source; the post-game review, asked once the game has ended, is fetched by `GamePage` (`useReview`, from the server or from beside a game file) and passed in as data, and its seam-3 test passes the recorded review (`fixtures/scripted-game.review.json`).

## Change the town

The Town view draws what the console's view says, so the rules live in pure code and Phaser only draws.

- **The map** is `frontend/assets/town/town.json`, a Tiled map with its tileset embedded; edit it in Tiled. The game reads the `props` layer (tiles with the `collides` property cannot be walked) and the `places` objects: the `square`, the `well`, the `hall`, a `door` per seat, the `den` and its `den window`, and the `lantern`, `chore` and `wander` spots (`frontend/src/core/town/plan.ts`). Each `chore` spot names the `kind` of Chore done there; a new kind goes in `CHORE_KINDS` (`plan.ts`) with its tool in `CHORE_TOOLS` (`game/looks.ts`). Then run `pnpm check:assets` and `pnpm test`.
- **New art** goes beside the map, credited in `ATTRIBUTION.md` (`pnpm check:assets` fails until it is), and is loaded in `frontend/src/game/looks.ts`.
- **Where Residents stand** is `layoutFor` (`core/town/layout.ts`), from the view and the stage (`stageOf` in `core/town/stage.ts`: what is said, voted and done this Phase), both tested from the recorded game. An event the town should show goes into the stage first; mystery mode hides what the stage never sees. The town walks everyone to the layout, and snaps after a seek.
- **A moment to play out** (an event playback waits for) goes in `BLOCKING` (`core/presentation.ts`) and gets its animation in `TownScene.play` (`game/TownScene.ts`), which tells playback when it is done.
- **The screenshot** compares only on Linux. `pnpm e2e:linux` runs the browser tests in Playwright's image, as CI does (it needs Docker); after changing how the town looks, `pnpm e2e:linux --update-snapshots` makes the new baseline to commit. When Playwright is upgraded, change the image's tag in `.github/workflows/ci.yml` to match.
