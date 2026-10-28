# Recipes

Step-by-step guides for the changes this codebase is built to absorb. Each recipe is done when its tests pass and the regenerated files are committed.

## Regenerate the shared contract

Run after any change to an event, a decision answer or an API model:

```
cd backend
uv run mm schema
uv run mm play --seed 1 --quiet --out ../fixtures/scripted-game.ndjson
uv run mm minds
cd ../frontend
pnpm gen:types
```

## Add an event type

1. Define the payload in `backend/src/mm/engine/events.py`: a `type` literal and a `visibility()` saying who may perceive it. Add it to the `EventPayload` union.
2. If it changes state, handle it in `GameState.apply` (`engine/state.py`). If it only records something, leave the fold alone.
3. Append it from the Phase that causes it (`orchestrator/phases/`), through `game.append`.
4. Decide how Agents read it: a line in `_line` or a fact in `_facts` (`agents/prompting.py`). `_line`, `GameState.apply` and the transcript's `describe` end in `assert_never`, so `mypy` fails until the new type has a case in each.
5. Regenerate the shared contract. TypeScript's exhaustive `switch` statements then fail to compile at every place that needs a case: the feed line (`ui/describeEvent.ts`), the view fold (`core/gameView.ts`) and `decider` (`core/mind.ts`), which names the Resident whose decision the event records. Add the transcript line in `cli/transcript.py`.
6. Write a seam-1 test for when the event is appended and who perceives it, and a seam-3 test if Spectators see it.

## Add a decision kind

1. Add the kind to `DecisionKind` and its answer, a `Decision` subclass, in `engine/decisions.py`.
2. Add its legality rule to `why_illegal` (`engine/rules.py`). Its options builder lives with the rules of its Phase, as `ballot_options` lives in `engine/vote.py`.
3. Teach `ScriptedBot` to answer it legally (`agents/scripted.py`).
4. Give LLM Agents what they need: an `AnswerSpec` with its safe default in `ANSWERS` (`agents/answers.py`), either `always(...)` one decision or a function of the request such as `any_option`, and an instructions template in `agents/prompts/decisions/`, listed in `DECISION_TEMPLATES` (`agents/prompting.py`). If the answer picks a Resident from a list, reuse the `Target` shape and its legality rule.
5. Ask for it from the Phase with `game.decide` (one Resident) or `game.decide_all` (several at once, answers in the order asked), and append the event it causes with `cause=` so the event names the decision. Every decision causes at least one event, even one that changes nothing (a Sheriff holding fire causes `SheriffHeldFire`), so the Mind inspector can list and explain it. The event's payload names the Resident who decided. Do not ask a Resident whose options are empty.
6. Add its label to `decisionLabel` (`frontend/src/ui/labels.ts`); the `Record` type will not compile until you do.
7. Write seam-1 tests that script the answers with a `Puppet`-style test decision source, and seam-2 tests with `FakeModel` for its fallback.

## Add a role

1. Add it to `Role` (`engine/roles.py`). Its side follows from `Role.side`.
2. Add a toggle to `GameConfig` and include it in `role_deck` (`engine/config.py`).
3. Its powers are decision kinds (see above), asked for by the Phase where they act.
4. Add its label to `roleLabel` (`frontend/src/ui/labels.ts`). The `Record` type will not compile until you do.

## Add a panel

1. Derive what it shows in `frontend/src/core` (pure, from events), not inside the component.
2. Render it from a component in `frontend/src/ui` and mount it in `GameConsole`.
3. Write a seam-3 test: render from the recorded fixture and assert what a Spectator sees, by role and accessible name.
