"""What a usable answer is for each decision kind, and the safe default when there is none.

An answer is usable when it has the right shape, breaks no rule and, once
scrubbed of anything from outside the game world, can be shown to everyone.
"""

import re
from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError

from mm.engine import Role
from mm.engine.decisions import (
    SKIP,
    Ballot,
    Bid,
    Decision,
    DecisionKind,
    DecisionRequest,
    LastWords,
    Reflection,
    Showdown,
    Statement,
)
from mm.engine.rules import why_illegal


class StatementAnswer(Statement):
    """An Agent's Statement, plus its own true role as a tripwire. The role is never shown."""

    my_role: Role = Field(description="Your own true role. Nobody else ever sees this field.")


@dataclass(frozen=True)
class AnswerSpec:
    shape: type[Decision]
    fallback: Decision
    """What happens when the Resident cannot decide: silence, a bid of 0, holding fire,
    a vote to skip, no last words or an empty reflection that changes nothing."""


ANSWERS: dict[DecisionKind, AnswerSpec] = {
    DecisionKind.STATEMENT: AnswerSpec(StatementAnswer, Statement.plain("(stays silent)")),
    DecisionKind.BID: AnswerSpec(Bid, Bid(urgency=0, reason="(no answer)")),
    DecisionKind.SHOWDOWN: AnswerSpec(
        Showdown, Showdown(fire=False, target=None, reason="(no answer)")
    ),
    DecisionKind.BALLOT: AnswerSpec(Ballot, Ballot(choice=SKIP)),
    DecisionKind.LAST_WORDS: AnswerSpec(LastWords, LastWords(text="(says nothing)")),
    DecisionKind.REFLECTION: AnswerSpec(
        Reflection, Reflection(journal_entry="", notebook="", suspicions=[])
    ),
}

OUTSIDE_WORLD = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"  # email addresses
    r"|\b[A-Za-z]:\\\S*"  # Windows paths
    r"|(?<!\w)/(?:home|Users|tmp|var)/\S*"  # Unix paths
)
"""Things an Agent may have glimpsed in its environment that must never reach the town."""


def answer_schema(kind: DecisionKind) -> dict[str, Any]:
    """The JSON Schema for one kind of answer, flattened so any draft-07 validator accepts it."""
    schema = ANSWERS[kind].shape.model_json_schema()
    definitions = schema.pop("$defs", {})
    flattened: dict[str, Any] = _without_titles(_inline(schema, definitions))
    return flattened


def read_answer(
    request: DecisionRequest, data: dict[str, Any] | None, own_role: Role
) -> Decision | str:
    """The decision in a model's answer, or why it cannot be used."""
    if data is None:
        return "the answer was not in the requested structure"
    try:
        decision = ANSWERS[request.kind].shape.model_validate(data)
    except ValidationError as error:
        return "; ".join(
            f"{'.'.join(map(str, problem['loc'])) or 'answer'}: {problem['msg']}"
            for problem in error.errors()
        )
    if problem := why_illegal(request, decision):
        return problem
    if isinstance(decision, StatementAnswer) and decision.my_role is not own_role:
        return f"your true role is {own_role.capitalize()}, not {decision.my_role.capitalize()}"
    return scrub(decision)


def scrub(decision: Decision) -> Decision:
    return type(decision).model_validate(_scrub(decision.model_dump()))


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return OUTSIDE_WORLD.sub("[hidden]", value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
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
