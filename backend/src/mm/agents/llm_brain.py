"""LLM Agents: Residents played by a language model, through one shared decision pipeline.

Every decision, whatever its kind, goes the same way: build the prompt from
what the Resident perceived, call the model, read the answer, and retry once
with the problem quoted if it is unusable. If it still is, or the model
refused or timed out, a safe default is used and the reason is reported. Each
attempt is recorded before the decision is returned.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from mm.agents.answers import ANSWERS, answer_schema, read_answer
from mm.agents.brain import Brain, BrainFactory
from mm.agents.calls import CallOutcome, CallRecorder, ModelCall
from mm.agents.prompting import build_prompt, prompt_version, retry_task
from mm.engine import Resident, Role
from mm.engine.decisions import Answer, Decision, DecisionRequest
from mm.engine.events import Event
from mm.engine.perception import briefing
from mm.llm import Effort, ModelProvider, ModelReply, ModelRequest

ATTEMPTS = 2


@dataclass(frozen=True)
class AgentSettings:
    model: str = "claude-haiku-5-5"
    effort: Effort = Effort.LOW


class LLMBrain:
    def __init__(
        self, provider: ModelProvider, settings: AgentSettings, record: CallRecorder, rng: Random
    ) -> None:
        self.provider, self.settings, self.record, self.rng = provider, settings, record, rng

    async def decide(self, request: DecisionRequest, view: Sequence[Event]) -> Answer:
        prompt = build_prompt(request, view, self.rng)
        schema = answer_schema(request.kind)
        own_role = briefing(view, request.resident).role
        problem: str | None = None
        for attempt in range(1, ATTEMPTS + 1):
            message = prompt.user_message(retry_task(prompt, problem) if problem else None)
            reply = await self.provider.complete(
                ModelRequest(
                    system=prompt.system,
                    prompt=message,
                    schema=schema,
                    model=self.settings.model,
                    effort=self.settings.effort,
                )
            )
            decision, problem, outcome = _interpret(request, reply, own_role)
            await self.record(
                self._call(
                    request=request,
                    attempt=attempt,
                    system=prompt.system,
                    prompt=message,
                    reply=reply,
                    outcome=outcome,
                    problem=problem,
                )
            )
            if decision is not None:
                return Answer(decision)
            if outcome != "invalid":
                break  # refusals, timeouts and errors are not worth a second try
        return Answer(ANSWERS[request.kind].fallback, fallback_reason=problem)

    def _call(
        self,
        *,
        request: DecisionRequest,
        attempt: int,
        system: str,
        prompt: str,
        reply: ModelReply,
        outcome: CallOutcome,
        problem: str | None,
    ) -> ModelCall:
        return ModelCall(
            decision_id=request.id,
            resident=request.resident,
            kind=request.kind,
            attempt=attempt,
            provider=self.provider.name,
            model=self.settings.model,
            effort=self.settings.effort,
            prompt_version=prompt_version(),
            system=system,
            prompt=prompt,
            outcome=outcome,
            problem=problem,
            raw_text=reply.text,
            answer=reply.data,
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
            cache_read_tokens=reply.usage.cache_read_tokens,
            cache_write_tokens=reply.usage.cache_write_tokens,
            cost_usd=reply.cost_usd,
            latency_ms=reply.latency_ms,
        )


def _interpret(
    request: DecisionRequest, reply: ModelReply, own_role: Role
) -> tuple[Decision | None, str | None, CallOutcome]:
    if reply.outcome != "ok":
        return None, reply.error or reply.outcome, reply.outcome
    answer = read_answer(request, reply.data, own_role)
    if isinstance(answer, str):
        return None, answer, "invalid"
    return answer, None, "ok"


def llm_agents(
    provider: ModelProvider, settings: AgentSettings, record: CallRecorder, seed: int
) -> BrainFactory:
    """A factory giving every Resident its own Agent, sharing one provider."""

    def make(resident: Resident) -> Brain:
        return LLMBrain(provider, settings, record, Random(f"{seed}:{resident.name}"))

    return make
