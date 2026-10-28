/* Generated from protocol/murdertown.schema.json by 'pnpm gen:types'. Do not edit. */

/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DecisionKind".
 */
export type DecisionKind =
  | "statement"
  | "bid"
  | "showdown"
  | "ballot"
  | "last_words"
  | "reflection"
  | "den_message"
  | "kill_vote"
  | "protect"
  | "investigate"
  | "recap"
  | "dusk_intent"
  | "conversation_message";
/**
 * How hard the model thinks before answering: more effort, slower and dearer answers.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Effort".
 */
export type Effort = "low" | "medium" | "high" | "max";
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
 * Dawn's news that the Murderers attacked someone the Doctor had protected.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "AttackThwarted".
 */
export interface AttackThwarted {
  type: "attack_thwarted";
  saved: string | null;
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
 * How urgently one Resident wants to make the next Statement on the Open floor.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "BidPlaced".
 */
export interface BidPlaced {
  type: "bid_placed";
  resident: string;
  urgency: number;
  reason: string;
}
/**
 * One message in a Conversation, heard only by the two Residents in it.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ConversationMessagePosted".
 */
export interface ConversationMessagePosted {
  type: "conversation_message_posted";
  speaker: string;
  partner: string;
  text: string;
  ends_conversation: boolean;
}
/**
 * Two Residents slip away to talk. Everyone sees that they met, but not who asked whom.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ConversationStarted".
 */
export interface ConversationStarted {
  type: "conversation_started";
  /**
   * @minItems 2
   * @maxItems 2
   */
  residents: [unknown, unknown];
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
 * One Murderer's message to the others, perhaps proposing tonight's Victim.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DenMessagePosted".
 */
export interface DenMessagePosted {
  den: string[];
  type: "den_message_posted";
  murderer: string;
  text: string;
  proposed_victim: string | null;
}
/**
 * What a Resident means to do at Dusk: talk, wander or do a chore. Only they know.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DuskIntentChosen".
 */
export interface DuskIntentChosen {
  type: "dusk_intent_chosen";
  resident: string;
  activity: "talk" | "wander" | "chore";
  partners: string[];
  topic: string;
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
    | BidPlaced
    | StatementMade
    | SheriffFired
    | SheriffHeldFire
    | BallotCast
    | VoteResolved
    | LastWordsSpoken
    | ResidentDied
    | DenMessagePosted
    | KillVoteCast
    | VictimChosen
    | ResidentProtected
    | ResidentInvestigated
    | AttackThwarted
    | RecapNarrated
    | DuskIntentChosen
    | ConversationStarted
    | ConversationMessagePosted
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
 * via the `definition` "GameConfig-Output".
 */
export interface GameConfig {
  residents: number;
  murderers: number;
  doctor: boolean;
  detective: boolean;
  sheriff: boolean;
  max_days: number;
  open_floor_statements: number;
  open_floor_seconds: number | null;
  sheriff_shoots_at: "showdown" | "night";
  detective_accuracy: number;
  dawn_names_the_saved: boolean;
  seed: number;
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
 * A Statement, with what it does: whom it names, accuses and defends, and any role claim.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "StatementMade".
 */
export interface StatementMade {
  type: "statement_made";
  speaker: string;
  text: string;
  part: "opening_round" | "open_floor";
  addressed: string[];
  accused: string[];
  defended: string[];
  claimed_role: Role | null;
}
/**
 * The Sheriff spends the single bullet. Whoever is hit, and perhaps the Sheriff, dies next.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "SheriffFired".
 */
export interface SheriffFired {
  type: "sheriff_fired";
  sheriff: string;
  target: string;
  hit_a_murderer: boolean;
}
/**
 * The Sheriff chose not to fire this time and keeps the bullet.
 *
 * It is recorded so every decision leaves a mark in the log. Only Spectators
 * perceive it: the town learns nothing, and the Sheriff already knows.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "SheriffHeldFire".
 */
export interface SheriffHeldFire {
  type: "sheriff_held_fire";
  sheriff: string;
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
 * What a banished Resident says before their role is revealed.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "LastWordsSpoken".
 */
export interface LastWordsSpoken {
  type: "last_words_spoken";
  resident: string;
  text: string;
}
/**
 * A death, announced to everyone with the dead Resident's role.
 *
 * A Resident is banished by Vote, shot by the Sheriff or murdered at Night; a
 * Sheriff who shoots a Town Resident dies of the backfire.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ResidentDied".
 */
export interface ResidentDied {
  type: "resident_died";
  resident: string;
  cause: "banished" | "shot" | "backfire" | "murdered";
  role: Role;
}
/**
 * One Murderer's choice of Victim; a lone Murderer's choice settles it.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "KillVoteCast".
 */
export interface KillVoteCast {
  den: string[];
  type: "kill_vote_cast";
  murderer: string;
  target: string;
}
/**
 * The Den's Victim: the most kill votes, with a tie drawn at random.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "VictimChosen".
 */
export interface VictimChosen {
  den: string[];
  type: "victim_chosen";
  victim: string;
}
/**
 * The Doctor's protection for the Night. If the Murderers attack this Resident, they live.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ResidentProtected".
 */
export interface ResidentProtected {
  type: "resident_protected";
  doctor: string;
  target: string;
}
/**
 * What the Detective learns about one Resident. It is not always right.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ResidentInvestigated".
 */
export interface ResidentInvestigated {
  type: "resident_investigated";
  detective: string;
  target: string;
  found_murderer: boolean;
}
/**
 * The narrator's short recap of the Day so far, told at Dawn.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "RecapNarrated".
 */
export interface RecapNarrated {
  type: "recap_narrated";
  text: string;
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
 * The decision behind an event: every model attempt at it, and the fallback if one was used.
 *
 * A decision made by a scripted bot has no attempts, because no model was asked.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Explanation".
 */
export interface Explanation {
  event: Event;
  attempts: ModelCall[];
  fallback_reason: string | null;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "ModelCall".
 */
export interface ModelCall {
  decision_id: string;
  resident: string;
  kind: DecisionKind;
  attempt: number;
  provider: string;
  model: string;
  effort: Effort;
  prompt_version: string;
  system: string;
  prompt: string;
  outcome: ("ok" | "refusal" | "timeout" | "error") | "invalid";
  problem: string | null;
  raw_text: string;
  answer: {
    [k: string]: unknown;
  } | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number | null;
  latency_ms: number;
  trace_id: string | null;
}
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameConfig-Input".
 */
export interface GameConfigInput {
  residents?: number;
  murderers?: number;
  doctor?: boolean;
  detective?: boolean;
  sheriff?: boolean;
  max_days?: number;
  open_floor_statements?: number;
  open_floor_seconds?: number | null;
  sheriff_shoots_at?: "showdown" | "night";
  detective_accuracy?: number;
  dawn_names_the_saved?: boolean;
  seed?: number;
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
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "JournalEntry".
 */
export interface JournalEntry {
  day: number;
  phase: Phase;
  text: string;
}
/**
 * What a Resident carries in mind from one decision to the next.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Memory".
 */
export interface Memory {
  notebook: string;
  journal: JournalEntry[];
  dossier: Suspicion[];
}
/**
 * One Resident's mind at one moment: who they are, what they remember, what they perceived.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Mind".
 */
export interface Mind {
  resident: string;
  role: Role;
  persona: Persona;
  teammates: string[];
  memory: Memory;
  perceived: Event[];
}
