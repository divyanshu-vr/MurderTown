# MurderTown

A social-deduction game in which every Resident of a small town is played by an LLM Agent with its own isolated memory, while humans watch. Murderers strike at Night; the Town debates, votes and banishes by Day.

Work in progress. The plan is [issue #1](https://github.com/divyanshu-vr/MurderTown/issues/1), built ticket by ticket.

## Run it

You need [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) (pnpm fetches the Node version the frontend needs).

```
cd backend && uv sync && uv run mm serve        # terminal 1: the API, which prints the Host's link
cd frontend && pnpm install && pnpm dev          # terminal 2: the web console
```

Open the link `mm serve` prints. It hands your browser the Host token, so you can set up games, pause, step and resume them, and watch them in full. Anyone else who opens the console watches in public scope: only what the whole town saw. `uv run mm new-game` starts a game from the terminal instead.

Watch at any pace: hold, step, change speed or skip to live (Space, the arrow keys, `-` and `=`, `L`). Every finished game has a replay link. `uv run mm export <game id>` writes a finished game to a game file, which the console replays with no server at `/replay?file=<its address>`.

Or play a game straight in the terminal: `cd backend && uv run mm play`.

## Layout

- `backend/`: game engine, decision sources, orchestration, storage and API ([details](backend/README.md))
- `frontend/`: the web console: the game list, the Host's setup form and controls, and every Spectator's view of a game
- `protocol/`: the backend-frontend protocol as JSON Schema; frontend types are generated from it
- `fixtures/`: a recorded game shared by backend and frontend tests
- `GLOSSARY.md`: the game's vocabulary
