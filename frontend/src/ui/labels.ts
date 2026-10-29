/** Every name the interface shows for a domain value, in one place. Vocabulary follows GLOSSARY.md. */
import type { FeedKind } from "../core/feedFilter";
import type { NumberField } from "../core/setup";
import type {
  Control,
  DecisionKind,
  Effort,
  GameConfigInput,
  GameSummary,
  ModelCall,
  PayloadOf,
  Phase,
  Review,
  Role,
  Side,
} from "../protocol";

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

export const statusLabel: Record<GameSummary["status"], string> = {
  running: "Playing",
  paused: "Paused",
  finished: "Finished",
  aborted: "Aborted",
  failed: "Failed",
};

export const controlLabel: Record<Control, string> = { pause: "Pause", step: "Step", resume: "Resume" };

export const sideLabel: Record<Side, string> = { town: "Town", murderers: "Murderers" };

export const numberLabel: Record<NumberField, string> = {
  residents: "Residents",
  murderers: "Murderers",
  max_days: "Days at most",
  open_floor_statements: "Open-floor Statements",
  open_floor_seconds: "Open-floor time limit (seconds)",
  detective_accuracy: "Detective accuracy",
};

export const effortLabel: Record<Effort, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  max: "Max",
};

export const sheriffFiresLabel: Record<NonNullable<GameConfigInput["sheriff_shoots_at"]>, string> = {
  showdown: "In each Day's Showdown",
  night: "At Night",
};

/** A role as a phrase: there are several Murderers and Civilians, but one of each power. */
export function aRole(role: Role): string {
  return `${role === "murderer" || role === "civilian" ? "a" : "the"} ${roleLabel[role]}`;
}

/** What a Statement did that made it a Lie, before whom it named or what it claimed. */
export const lieLabel: Record<Review["lies"][number]["kind"], string> = {
  false_role: "claimed to be",
  accused_trusted: "accused",
  defended_suspected: "defended",
};

/** A Resident's name, marked if they are dead. */
export function residentName(name: string, dead: boolean): string {
  return dead ? `${name} (dead)` : name;
}

/** An Equivalent cost, to the hundredth of a cent. */
export function dollars(amount: number): string {
  return `$${amount.toFixed(4)}`;
}

/** An expected cost, to the cent: an estimate is no more precise than that. */
export function aboutDollars(amount: number): string {
  return amount > 0 && amount < 0.005 ? "under $0.01" : `$${amount.toFixed(2)}`;
}

/** The kinds of line the feed can be filtered by. */
export const feedKindLabel: Record<FeedKind, string> = {
  public: "Public",
  private: "Private",
  night: "Night",
  system: "System",
};

/** How a Dusk activity reads after "means to". */
export const activityLabel: Record<PayloadOf<"dusk_intent_chosen">["activity"], string> = {
  talk: "talk",
  wander: "wander the town",
  chore: "do a chore",
};
