/* Generated from protocol/murdertown.schema.json by 'pnpm gen:types'. Do not edit. */

/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DecisionKind".
 */
export type DecisionKind = "statement" | "ballot" | "reflection";
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Phase".
 */
export type Phase = "setup" | "dawn" | "discussion" | "showdown" | "vote" | "dusk" | "night" | "ended";
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Role".
 */
export type Role = "murderer" | "doctor" | "detective" | "sheriff" | "civilian";
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Side".
 */
export type Side = "town" | "murderers";

export interface MurderTownProtocol {
  [k: string]: unknown;
}
/**
 * One Resident's ballot, revealed once every ballot of the Vote has been cast.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "BallotCast".
 */
export interface BallotCast {
  type: "ballot_cast";
  voter: string;
  target: string | null;
}
/**
 * A decision source could not give a usable answer, so a safe default was used instead.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DecisionFellBack".
 */
export interface DecisionFellBack {
  type: "decision_fell_back";
  resident: string;
  kind: DecisionKind;
  reason: string;
}
/**
 * One entry in a game's log: a payload stamped with its place in the game.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Event".
 */
export interface Event {
  seq: number;
  day: number;
  phase: Phase;
  visibility: Visibility;
  decision_id: string | null;
  payload:
    | GameStarted
    | RoleAssigned
    | PhaseStarted
    | StatementMade
    | BallotCast
    | VoteResolved
    | ResidentDied
    | ReflectionWritten
    | DecisionFellBack
    | GameEnded;
}
/**
 * Who may perceive an event: everyone, a named set of Residents, or Spectators only.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Visibility".
 */
export interface Visibility {
  scope: "everyone" | "residents" | "spectators";
  residents: string[];
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameStarted".
 */
export interface GameStarted {
  type: "game_started";
  config: GameConfig;
  residents: Resident[];
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameConfig".
 */
export interface GameConfig {
  residents?: number;
  murderers?: number;
  doctor?: boolean;
  detective?: boolean;
  sheriff?: boolean;
  max_days?: number;
  seed?: number;
}
/**
 * A character in the town. The seat fixes their house and their place in every ordering.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Resident".
 */
export interface Resident {
  name: string;
  seat: number;
  occupation: string;
}
/**
 * A Resident learns their role and persona. Murderers also learn who their teammates are.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "RoleAssigned".
 */
export interface RoleAssigned {
  type: "role_assigned";
  resident: string;
  role: Role;
  persona: Persona;
  teammates: string[];
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Persona".
 */
export interface Persona {
  occupation: string;
  temperament: string;
  speaking_style: string;
  quirk: string;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "PhaseStarted".
 */
export interface PhaseStarted {
  type: "phase_started";
  day: number;
  phase: Phase;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "StatementMade".
 */
export interface StatementMade {
  type: "statement_made";
  speaker: string;
  text: string;
  part: "opening_round" | "open_floor";
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "VoteResolved".
 */
export interface VoteResolved {
  type: "vote_resolved";
  tally: {
    [k: string]: number;
  };
  skips: number;
  banished: string | null;
}
/**
 * A death, announced to everyone with the dead Resident's role.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ResidentDied".
 */
export interface ResidentDied {
  type: "resident_died";
  resident: string;
  cause: "banished";
  role: Role;
}
/**
 * A Resident's private journal entry, rewritten notebook and changed suspicions.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ReflectionWritten".
 */
export interface ReflectionWritten {
  type: "reflection_written";
  resident: string;
  journal_entry: string;
  notebook: string;
  suspicions: Suspicion[];
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Suspicion".
 */
export interface Suspicion {
  /**
   * Another Resident's name.
   */
  resident: string;
  /**
   * 0 = certainly innocent, 100 = certainly a Murderer.
   */
  suspicion: number;
  /**
   * Why, in a few words.
   */
  note: string;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameEnded".
 */
export interface GameEnded {
  type: "game_ended";
  winner: Side;
  reason: string;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "EventPage".
 */
export interface EventPage {
  events: Event[];
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameCreated".
 */
export interface GameCreated {
  id: string;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameSummary".
 */
export interface GameSummary {
  id: string;
  status: "running" | "finished" | "failed";
  config: GameConfig;
  winner: Side | null;
  last_seq: number;
}
