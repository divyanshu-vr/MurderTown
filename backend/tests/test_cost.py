"""What model calls cost: the price table, each call's record, and the game's cost report.

Equivalent cost is what the calls would cost at the Claude API's list prices,
whichever provider made them. The expected figures for real calls are Claude
Code's own `total_cost_usd` for those calls (measured 2026-10-28).
"""

import json
from collections.abc import Iterator, Sequence

import pytest
from fastapi.testclient import TestClient

from mm.agents import AgentSettings, BrainFactory, CallRecorder, Cost, ModelCall, llm_agents
from mm.engine import GameConfig
from mm.engine.decisions import DecisionKind
from mm.llm import ModelReply, ModelRequest, Usage
from mm.llm.prices import equivalent_cost
from mm.orchestrator.narrator import NARRATOR
from tests.conftest import serving, start_game, wait_until_finished
from tests.support import FakeModel, answer_kind, played_by, sensible_answer

CONFIG = GameConfig(residents=6, murderers=1, max_days=1, seed=13)

FIRST_LIVE_CALL = Usage(input_tokens=2, output_tokens=513, cache_write_1h_tokens=2634)
"""A live Haiku Statement from ticket #8: Claude Code put its cost at $0.0007835."""

SECOND_LIVE_CALL = Usage(input_tokens=2, output_tokens=62, cache_write_1h_tokens=959)
"""A live Haiku probe from ticket #9: Claude Code put its cost at $0.000223."""


@pytest.mark.parametrize(
    ("model", "usage", "dollars"),
    [
        ("claude-haiku-5-5", FIRST_LIVE_CALL, 0.0007835),
        ("claude-haiku-5-5", SECOND_LIVE_CALL, 0.000223),
        ("claude-haiku-5-5", Usage(cache_read_tokens=1_000_000), 0.01),
        ("claude-opus-5-5", Usage(cache_read_tokens=1_000_000), 0.20),
        ("claude-haiku-5-5", Usage(cache_write_5m_tokens=1_000_000), 0.125),
        ("claude-sonnet-5-5", Usage(input_tokens=1_000_000, output_tokens=1_000_000), 12.00),
    ],
)
def test_the_price_table_gives_each_calls_equivalent_cost(
    model: str, usage: Usage, dollars: float
) -> None:
    assert equivalent_cost(model, usage) == pytest.approx(dollars)


async def test_each_model_call_records_its_cost_from_the_price_table() -> None:
    def live_sized(request: ModelRequest) -> ModelReply:
        reply = sensible_answer(request)
        return ModelReply(outcome="ok", data=reply.data, text=reply.text, usage=FIRST_LIVE_CALL)

    _, calls = await played_by(FakeModel(live_sized), CONFIG)

    assert calls
    assert all(call.cost_usd == pytest.approx(0.0007835) for call in calls)
    assert {call.cache_write_tokens for call in calls} == {2634}


def test_agents_refuse_a_model_with_no_price_before_the_game_starts() -> None:
    async def record(call: ModelCall) -> None: ...

    with pytest.raises(ValueError, match="claude-imaginary-1"):
        llm_agents(FakeModel(), AgentSettings(model="claude-imaginary-1"), record, seed=1)


def varied_usage(request: ModelRequest) -> ModelReply:
    """Sensible answers whose tokens differ by decision kind, with both kinds of cache write.
    Every first ballot is unusable and every Dusk intent refused, so retries and refusals count."""
    kind = answer_kind(request)
    n = list(DecisionKind).index(kind) + 1
    usage = Usage(
        input_tokens=10 * n,
        output_tokens=3 * n,
        cache_read_tokens=5 * n,
        cache_write_5m_tokens=n % 2,
        cache_write_1h_tokens=2 * n,
    )
    if kind is DecisionKind.DUSK_INTENT:
        return ModelReply(outcome="refusal", data=None, text="", usage=usage, error="declined")
    if kind is DecisionKind.BALLOT and "could not be used" not in request.prompt:
        answer: dict[str, object] = {"target": "Nobody", "reason": "a hunch"}
    else:
        answer = sensible_answer(request).data or {}
    return ModelReply(outcome="ok", data=answer, text=json.dumps(answer), usage=usage)


@pytest.fixture
def recorded(database_url: str) -> Iterator[tuple[TestClient, list[ModelCall]]]:
    """An API whose games are played by Agents, plus every model call they recorded."""
    calls: list[ModelCall] = []

    def agents(
        config: GameConfig, record: CallRecorder, replay: Sequence[ModelCall]
    ) -> BrainFactory:
        async def keep(call: ModelCall) -> None:
            calls.append(call)
            await record(call)

        return llm_agents(FakeModel(varied_usage), AgentSettings(), keep, config.seed)

    with serving(database_url, agents) as client:
        yield client, calls


def summed(calls: list[ModelCall]) -> object:
    """The cost of some calls as the API sends it, with the dollars compared approximately."""
    return pytest.approx(Cost.of(calls).model_dump(mode="json"))


def test_the_cost_report_adds_up_every_recorded_model_call(
    recorded: tuple[TestClient, list[ModelCall]],
) -> None:
    client, calls = recorded
    game_id = start_game(client, {"residents": 8, "murderers": 2, "max_days": 2, "seed": 4})
    wait_until_finished(client, game_id)

    report = client.get(f"/games/{game_id}/cost").json()

    narrated = [call for call in calls if call.resident == NARRATOR.name]
    assert narrated, "the narrator recaps the second Dawn"
    assert {call.outcome for call in calls} >= {"ok", "invalid", "refusal"}
    assert report["total"] == summed(calls)
    assert report["narrator"] == summed(narrated)
    assert set(report["residents"]) == {call.resident for call in calls} - {NARRATOR.name}
    for name, cost in report["residents"].items():
        assert cost == summed([call for call in calls if call.resident == name])


def test_only_full_scope_may_see_what_a_game_cost(
    recorded: tuple[TestClient, list[ModelCall]],
) -> None:
    client, _ = recorded
    game_id = start_game(client, {"residents": 6, "murderers": 1, "max_days": 1, "seed": 4})
    wait_until_finished(client, game_id)

    assert client.get(f"/games/{game_id}/cost?scope=public").status_code == 403
    assert client.get("/games/no-such-game/cost").status_code == 404


def test_cache_hit_rate_is_the_share_of_prompt_tokens_read_from_the_cache() -> None:
    cost = Cost(calls=2, input_tokens=10, cache_read_tokens=30, cache_write_tokens=60)

    assert cost.prompt_tokens == 100
    assert cost.cache_hit_rate == pytest.approx(0.3)
    assert Cost().cache_hit_rate is None
