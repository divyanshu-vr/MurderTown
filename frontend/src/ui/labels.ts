/** Every name the interface shows for a domain value, in one place. Vocabulary follows GLOSSARY.md. */
import type { DecisionKind, ModelCall, PayloadOf, Phase, Role, Side } from "../protocol";

export const phaseLabel: Record<Phase, string> = {
  setup: "Setting up",
  dawn: "Dawn",
  discussion: "Discussion",
  showdown: "Showdown",
  vote: "Vote",
  dusk: "Dusk",
  night: "Night",
  ended: "Game over",
};

export const roleLabel: Record<Role, string> = {
  murderer: "Murderer",
  doctor: "Doctor",
  detective: "Detective",
  sheriff: "Sheriff",
  civilian: "Civilian",
};

export const victoryLabel: Record<Side, string> = {
  town: "The Town wins",
  murderers: "The Murderers win",
};

type Cause = PayloadOf<"resident_died">["cause"];

/** How a dead Resident is marked in the roster. */
export const fateLabel: Record<Cause, string> = {
  banished: "Banished",
  shot: "Shot",
  backfire: "Backfire",
  murdered: "Murdered",
};

/** How the feed tells of a death. */
export const deathLabel: Record<Cause, string> = {
  banished: "leaves town forever",
  shot: "falls to the Sheriff's bullet",
  backfire: "is struck down by the backfire",
  murdered: "is found murdered",
};

export const decisionLabel: Record<DecisionKind, string> = {
  statement: "Statement",
  bid: "bid",
  showdown: "Showdown choice",
  ballot: "ballot",
  last_words: "last words",
  reflection: "reflection",
  den_message: "Den message",
  kill_vote: "kill vote",
  protect: "protection",
  investigate: "investigation",
  recap: "recap",
  dusk_intent: "Dusk intent",
  conversation_message: "Conversation message",
};

/** What came of one model attempt at a decision. */
export const attemptLabel: Record<ModelCall["outcome"], string> = {
  ok: "a usable answer",
  invalid: "an answer the game could not use",
  refusal: "the model refused",
  timeout: "no answer in time",
  error: "the call failed",
};

/** When something happened, as the Mind inspector dates journal entries and decisions. */
export function whenLabel(day: number, phase: Phase): string {
  return `Day ${day}, ${phaseLabel[phase]}`;
}

/** How a Dusk activity reads after "means to". */
export const activityLabel: Record<PayloadOf<"dusk_intent_chosen">["activity"], string> = {
  talk: "talk",
  wander: "wander the town",
  chore: "do a chore",
};
