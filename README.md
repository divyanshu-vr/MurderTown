# MurderTown

A social-deduction game in which every Resident of a small town is played by an LLM Agent with its own isolated memory, while humans watch. Murderers strike at Night; the Town debates, votes and banishes by Day.

Work in progress. The plan is [issue #1](https://github.com/divyanshu-vr/MurderTown/issues/1), built ticket by ticket.

## Run it

You need [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) (pnpm fetches the Node version the frontend needs).

```
cd backend && uv sync && uv run mm serve        # terminal 1: the API
cd frontend && pnpm install && pnpm dev          # terminal 2: the web console
cd backend && uv run mm new-game                 # terminal 3: start a game, open the printed link
```

Or play a game straight in the terminal: `cd backend && uv run mm play`.

## Layout

- `backend/`: game engine, decision sources, orchestration, storage and API ([details](backend/README.md))
- `frontend/`: the Spectator's web console
- `protocol/`: the backend-frontend protocol as JSON Schema; frontend types are generated from it
- `fixtures/`: a recorded game shared by backend and frontend tests
- `GLOSSARY.md`: the game's vocabulary
