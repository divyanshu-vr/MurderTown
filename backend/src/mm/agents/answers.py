"""What a usable answer is for each decision kind, and the safe default when there is none.

An answer is usable when it has the right shape, breaks no rule and, once
scrubbed of anything from outside the game world, can be shown to everyone.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any, cast

from pydantic import Field, ValidationError

from mm.engine import Role
from mm.engine.decisions import (
    SKIP,
    Bid,
    ConversationMessage,
    Decision,
    DecisionKind,
    DecisionRequest,
    DenMessage,
    DuskIntent,
    LastWords,
    Recap,
    Reflection,
    Showdown,
    Statement,
    Target,
)
from mm.engine.rules import why_illegal


class StatementAnswer(Statement):
    """An Agent's Statement, plus its own true role as a tripwire. The role is never shown."""

    my_role: Role = Field(description="Your own true role. Nobody else ever sees this field.")


Fallback = Callable[[DecisionRequest, Random], Decision]
"""What a Resident does when they cannot decide, given what they were asked."""


def always(decision: Decision) -> Fallback:
    """A fallback that is the same whatever was asked."""
    return lambda request, rng: decision


def any_option(request: DecisionRequest, rng: Random) -> Decision:
    """A random legal option: what happens to a Night choice nobody could make."""
    return Target(target=rng.choice(request.options), reason="(no answer)")


@dataclass(frozen=True)
class AnswerSpec:
    shape: type[Decision]
    fallback: Fallback
    """Silence, a bid of 0, holding fire, a vote to skip, no last words, an empty
    reflection that changes nothing, a random legal Night choice, wandering at
    Dusk, or ending the Conversation."""


ANSWERS: dict[DecisionKind, AnswerSpec] = {
    DecisionKind.STATEMENT: AnswerSpec(StatementAnswer, always(Statement.plain("(stays silent)"))),
    DecisionKind.BID: AnswerSpec(Bid, always(Bid(urgency=0, reason="(no answer)"))),
    DecisionKind.SHOWDOWN: AnswerSpec(
        Showdown, always(Showdown(fire=False, target=None, reason="(no answer)"))
    ),
    DecisionKind.BALLOT: AnswerSpec(Target, always(Target(target=SKIP, reason="(no answer)"))),
    DecisionKind.LAST_WORDS: AnswerSpec(LastWords, always(LastWords(text="(says nothing)"))),
    DecisionKind.REFLECTION: AnswerSpec(
        Reflection, always(Reflection(journal_entry="", notebook="", suspicions=[]))
    ),
    DecisionKind.DEN_MESSAGE: AnswerSpec(
        DenMessage, always(DenMessage(text="(says nothing)", proposed_victim=None))
    ),
    DecisionKind.KILL_VOTE: AnswerSpec(Target, any_option),
    DecisionKind.PROTECT: AnswerSpec(Target, any_option),
    DecisionKind.INVESTIGATE: AnswerSpec(Target, any_option),
    DecisionKind.RECAP: AnswerSpec(Recap, always(Recap(text="Another Day dawns over the town."))),
    DecisionKind.DUSK_INTENT: AnswerSpec(
        DuskIntent, always(DuskIntent(activity="wander", partners=[], topic=""))
    ),
    DecisionKind.CONVERSATION_MESSAGE: AnswerSpec(
        ConversationMessage,
        always(ConversationMessage(text="(says nothing)", end_conversation=True)),
    ),
}

OUTSIDE_WORLD = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"  # email addresses
    r"|\b[A-Za-z]:\\\S*"  # Windows paths
    r"|(?<!\w)/(?:home|Users|tmp|var)/\S*"  # Unix paths
)
"""Things an Agent may have glimpsed in its environment that must never reach the town."""


def answer_formats(kinds: Sequence[DecisionKind]) -> str:
    """How to answer each of these kinds of decision, one line each: its name and JSON Schema."""
    return "\n".join(
        f"- `{kind}`: {json.dumps(answer_schema(kind), separators=(',', ':'))}" for kind in kinds
    )


def answer_schema(kind: DecisionKind) -> dict[str, Any]:
    """The JSON Schema for one kind of answer, flattened so any draft-07 validator accepts it."""
    schema = ANSWERS[kind].shape.model_json_schema()
    definitions = schema.pop("$defs", {})
    flattened: dict[str, Any] = _without_titles(_inline(schema, definitions))
    return flattened


def read_answer(
    request: DecisionRequest, data: dict[str, Any] | None, own_role: Role | None
) -> Decision | str:
    """The decision in a model's answer, or why it cannot be used.

    `own_role` is the Resident's true role, checked against a Statement's tripwire;
    the narrator has none.
    """
    if data is None:
        return "the answer was not in the requested structure"
    try:
        decision = ANSWERS[request.kind].shape.model_validate(_unwrapped(data))
    except ValidationError as error:
        return "; ".join(
            f"{'.'.join(map(str, problem['loc'])) or 'answer'}: {problem['msg']}"
            for problem in error.errors()
        )
    if problem := why_illegal(request, decision):
        return problem
    if isinstance(decision, StatementAnswer) and own_role and decision.my_role is not own_role:
        return f"your true role is {own_role.capitalize()}, not {decision.my_role.capitalize()}"
    return type(decision).model_validate(scrubbed(decision.model_dump()))


def _unwrapped(data: dict[str, Any]) -> dict[str, Any]:
    """An answer nested one level down, as {"ballot": {...}}, taken out. A model sometimes nests
    its answer under its format's name or a field's, and no answer is one field holding an
    object."""
    inner = next(iter(data.values())) if len(data) == 1 else None
    return cast(dict[str, Any], inner) if isinstance(inner, dict) else data


def scrubbed[T](value: T) -> T:
    """Text, or JSON-like data, with anything from outside the game world hidden.

    The value keeps its shape, so a string stays a string and a dict a dict.
    """
    return cast(T, _scrubbed(value))


def _scrubbed(value: Any) -> Any:
    if isinstance(value, str):
        return OUTSIDE_WORLD.sub("[hidden]", value)
    if isinstance(value, dict):
        return {key: _scrubbed(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrubbed(item) for item in value]
    return value


def _inline(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
        return {key: _inline(value, definitions) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline(item, definitions) for item in node]
    return node


def _without_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _without_titles(value) for key, value in node.items() if key != "title"}
    if isinstance(node, list):
        return [_without_titles(item) for item in node]
    return node
