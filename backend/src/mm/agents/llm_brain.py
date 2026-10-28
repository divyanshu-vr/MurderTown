"""LLM Agents: Residents played by a language model, through one shared decision pipeline.

Every decision, whatever its kind, goes the same way: build the prompt from
what the Resident perceived, call the model, read the answer, and retry once
with the problem quoted if it is unusable. If it still is, or the model
refused, a safe default is used and the reason is reported. If the model gave no
answer at all (it timed out or failed), the decision fails and the game stops.
Each attempt is recorded before the decision is returned or fails, with anything
from outside the game world hidden, because records are shown to Spectators.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

import structlog

from mm.agents.answers import ANSWERS, answer_schema, read_answer, scrubbed
from mm.agents.brain import Brain, BrainFactory, ModelFailureError
from mm.agents.calls import CallOutcome, CallRecorder, ModelCall, label_generation
from mm.agents.prompting import build_prompt, prompt_version, retry_task
from mm.engine import Resident, Role
from mm.engine.decisions import Answer, Decision, DecisionRequest
from mm.engine.events import Event
from mm.engine.perception import assignment
from mm.llm import Effort, ModelProvider, ModelReply, ModelRequest
from mm.llm.prices import equivalent_cost, price_of
from mm.observability import tracing

logger = structlog.get_logger(__name__)

ATTEMPTS = 2

LOGGED = {"kind", "attempt", "outcome", "input_tokens", "output_tokens", "cache_read_tokens",
          "cost_usd", "latency_ms"}  # fmt: skip
"""What a model call's log line says; the prompt and answer stay in the record and the trace."""


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
        assigned = assignment(view, request.resident)  # the narrator has no role
        own_role = assigned.role if assigned else None
        problem: str | None = None
        for attempt in range(1, ATTEMPTS + 1):
            message = prompt.user_message(retry_task(prompt, problem) if problem else None)
            with tracing.tracer().start_as_current_span(
                f"{request.kind} attempt {attempt}"
            ) as span:
                reply = await self._complete(
                    ModelRequest(
                        system=prompt.system,
                        prompt=message,
                        schema=schema,
                        model=self.settings.model,
                        effort=self.settings.effort,
                    )
                )
                decision, problem, outcome = _interpret(request, reply, own_role)
                call = self._call(
                    request=request,
                    attempt=attempt,
                    system=prompt.system,
                    prompt=message,
                    reply=reply,
                    outcome=outcome,
                    problem=problem,
                    trace_id=tracing.trace_id_of(span),
                )
                label_generation(span, call)
            logger.info("model call", **call.model_dump(include=LOGGED))
            await self.record(call)
            if decision is not None:
                return Answer(decision)
            if outcome in ("timeout", "error"):
                raise ModelFailureError(request, problem or outcome)
            if outcome == "refusal":
                break  # a refusal is not worth a second try
        return Answer(ANSWERS[request.kind].fallback(request, self.rng), fallback_reason=problem)

    async def _complete(self, request: ModelRequest) -> ModelReply:
        """The provider's reply. A provider that raises instead of replying has failed."""
        try:
            return await self.provider.complete(request)
        except Exception as error:  # whatever went wrong, the game reports it
            return ModelReply.failure(str(error) or repr(error))

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
        trace_id: str | None,
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
            raw_text=scrubbed(reply.text),
            answer=scrubbed(reply.data),
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
            cache_read_tokens=reply.usage.cache_read_tokens,
            cache_write_tokens=reply.usage.cache_write_tokens,
            cost_usd=equivalent_cost(self.settings.model, reply.usage),
            latency_ms=reply.latency_ms,
            trace_id=trace_id,
        )


def _interpret(
    request: DecisionRequest, reply: ModelReply, own_role: Role | None
) -> tuple[Decision | None, str | None, CallOutcome]:
    """The decision in a reply, or why there is none.

    A problem can quote the model's own words, and it travels into the retry
    prompt, the call record and the fallback reason, so it is scrubbed too.
    """
    if reply.outcome != "ok":
        return None, scrubbed(reply.error or reply.outcome), reply.outcome
    answer = read_answer(request, reply.data, own_role)
    if isinstance(answer, str):
        return None, scrubbed(answer), "invalid"
    return answer, None, "ok"


def llm_agents(
    provider: ModelProvider, settings: AgentSettings, record: CallRecorder, seed: int
) -> BrainFactory:
    """A factory giving every Resident its own Agent, sharing one provider.

    A model with no price is refused here, before the game starts.
    """
    price_of(settings.model)

    def make(resident: Resident) -> Brain:
        return LLMBrain(provider, settings, record, Random(f"{seed}:{resident.name}"))

    return make
