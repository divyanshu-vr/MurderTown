/** Every name the interface shows for a domain value, in one place. Vocabulary follows GLOSSARY.md. */
import type { DecisionKind, PayloadOf, Phase, Role, Side } from "../protocol";

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
};

/** How the feed tells of a death. */
export const deathLabel: Record<Cause, string> = {
  banished: "leaves town forever",
  shot: "falls to the Sheriff's bullet",
  backfire: "is struck down by the backfire",
};

export const decisionLabel: Record<DecisionKind, string> = {
  statement: "Statement",
  bid: "bid",
  showdown: "Showdown choice",
  ballot: "ballot",
  last_words: "last words",
  reflection: "reflection",
};
