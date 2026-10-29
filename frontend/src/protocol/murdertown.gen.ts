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
 * How hard a Resident's Agent thinks before answering: more effort, slower and dearer.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Effort".
 */
export type Effort = "low" | "medium" | "high" | "max";
/**
 * What the Host may do to a game being played: hold it before its next batch of
 * decisions, let one more batch through a held game, or let it run on.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Control".
 */
export type Control = "pause" | "step" | "resume";
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Phase".
 */
export type Phase = "setup" | "dawn" | "discussion" | "showdown" | "vote" | "dusk" | "night" | "ended";
/**
 * How hard a Resident's Agent thinks before answering: more effort, slower and dearer.
 */
export type Effort1 = "low" | "medium" | "high" | "max";
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
/**
 * How hard a Resident's Agent thinks before answering: more effort, slower and dearer.
 */
export type Effort2 = "low" | "medium" | "high" | "max";

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
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "CallPage".
 */
export interface CallPage {
  calls: CallSummary[];
}
/**
 * One model call without its words: whose decision, which attempt, how it went and what it
 * took. What a list of many calls shows; the whole `ModelCall` adds the prompt and the answer,
 * and why an answer could not be used.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "CallSummary".
 */
export interface CallSummary {
  decision_id: string;
  resident: string;
  kind: DecisionKind;
  attempt: number;
  provider: string;
  model: string;
  effort: Effort;
  prompt_version: string;
  outcome: ("ok" | "refusal" | "timeout" | "error") | "invalid";
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cache_write_1h_tokens?: number;
  cost_usd: number;
  latency_ms: number;
  trace_id: string | null;
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
  residents: [string, string];
}
/**
 * What some model calls used and cost together: the cost meter's numbers.
 *
 * Prompt tokens are every token the model read, whether billed as plain input,
 * read from the cache or written to it.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Cost".
 */
export interface Cost {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number;
  prompt_tokens: number;
  /**
   * The share of prompt tokens read from the cache, or None before any prompt.
   */
  cache_hit_rate: number | null;
}
/**
 * What a game's model calls cost: in all, for each Resident, and for the narrator,
 * who is not a Resident. The Residents' rows and the narrator's add up to the total.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "CostReport".
 */
export interface CostReport {
  total: Cost;
  residents: {
    [k: string]: Cost;
  };
  narrator: Cost;
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
 * The model gave no answer at all to a decision, so the game is aborted right after. No
 * Resident perceives it, so only full scope shows it: whose decision it was, and of what
 * kind, could reveal a Night role.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "DecisionUnanswered".
 */
export interface DecisionUnanswered {
  type: "decision_unanswered";
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
 * A game's Expected cost, by model, and how many Days the paper game ran.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Estimate".
 */
export interface Estimate {
  usd: number;
  by_model: {
    [k: string]: number;
  };
  days: number;
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
    | GameConfigured
    | GameStarted
    | RoleAssigned
    | PhaseStarted
    | BidPlaced
    | StatementMade
    | OpenFloorTimedOut
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
    | RolesRevealed
    | GameEnded
    | DecisionUnanswered
    | GameAborted;
}
/**
 * Who may perceive an event: everyone, a named set of Residents, or no Resident at all
 * (`spectators`). Public scope shows only what everyone perceives; full scope shows it all.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Visibility".
 */
export interface Visibility {
  scope: "everyone" | "residents" | "spectators";
  residents: string[];
}
/**
 * Everything the Host chose, seed and lineup included. No Resident perceives it, so only
 * full scope shows it: casting follows from the seed, so knowing it would tell every role.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameConfigured".
 */
export interface GameConfigured {
  type: "game_configured";
  config: GameConfig;
}
/**
 * Everything the Host chooses before a game starts: its rules, its seed and who plays.
 *
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
  lineup: Lineup;
}
/**
 * Who plays each Resident. A seat's own choice wins, then its side's, then everyone's;
 * the narrator follows everyone's.
 */
export interface Lineup {
  everyone: PlayedBy;
  murderers: PlayedBy1 | null;
  town: PlayedBy1 | null;
  seats: {
    [k: string]: PlayedBy1;
  };
}
/**
 * Who plays a Resident: an Agent on a provider's model, (`"scripted"`) a scripted bot, or
 * (`"prober"`) a scripted bot that tries a prompt injection on the others.
 * The default is an Agent on Claude Haiku, on the Host's subscription unless an API key is set.
 */
export interface PlayedBy {
  provider: string;
  model: string;
  effort: Effort1;
}
/**
 * Who plays a Resident: an Agent on a provider's model, (`"scripted"`) a scripted bot, or
 * (`"prober"`) a scripted bot that tries a prompt injection on the others.
 * The default is an Agent on Claude Haiku, on the Host's subscription unless an API key is set.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "PlayedBy-Output".
 */
export interface PlayedBy1 {
  provider: string;
  model: string;
  effort: Effort1;
}
/**
 * Who lives in the town, and the rules everyone plays by.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameStarted".
 */
export interface GameStarted {
  type: "game_started";
  rules: Rules;
  residents: Resident[];
}
/**
 * The rules of one game, which everyone in town knows.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Rules".
 */
export interface Rules {
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
 * `asked` is the living Resident it asks to answer next, also among those it addresses.
 * `answering` says its speaker took the Open floor to answer, by Right of reply or a 4
 * that counted, so it starts no answer of its own. `seconds_left` is how long the Open
 * floor's time limit had left when it was made, so Spectators' countdowns follow the
 * server's clock; None in the Opening round or without a limit.
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
  asked: string | null;
  answering: boolean;
  accused: string[];
  defended: string[];
  claimed_role: Role | null;
  seconds_left: number | null;
}
/**
 * The Open floor's time limit ended it, before its Statement cap or two quiet Turns.
 *
 * Recorded because it depends on the clock: a resumed game replays the record.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "OpenFloorTimedOut".
 */
export interface OpenFloorTimedOut {
  type: "open_floor_timed_out";
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
 * As a side wins, every role becomes public, so the story ends for every Spectator and
 * for the town. Only the roles: the Den, the Night actions and private Conversations stay
 * as hidden as they were.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "RolesRevealed".
 */
export interface RolesRevealed {
  type: "roles_revealed";
  roles: {
    [k: string]: Role;
  };
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
 * The game stopped before either side won: a decision got no answer, or the game itself
 * failed. `reason` is only the problem, such as a timeout, never the decision itself, so the
 * whole town may see the game stop.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameAborted".
 */
export interface GameAborted {
  type: "game_aborted";
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
 * One attempt at one decision, whole: the prompt it was given and what came back.
 *
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
  outcome: ("ok" | "refusal" | "timeout" | "error") | "invalid";
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cache_write_1h_tokens?: number;
  cost_usd: number;
  latency_ms: number;
  trace_id: string | null;
  system: string;
  prompt: string;
  raw_text: string;
  answer: {
    [k: string]: unknown;
  } | null;
  problem: string | null;
}
/**
 * A Statement claiming a role that is not the speaker's.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "FalseClaim".
 */
export interface FalseClaim {
  kind: "false_role";
  seq: number;
  speaker: string;
  said: string;
  claimed_role: Role;
  true_role: Role;
}
/**
 * Everything the Host chooses before a game starts: its rules, its seed and who plays.
 *
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
  /**
   * Left out, the server draws one at random.
   */
  seed?: number;
  lineup?: LineupInput;
}
/**
 * Who plays each Resident. A seat's own choice wins, then its side's, then everyone's;
 * the narrator follows everyone's.
 */
export interface LineupInput {
  everyone?: PlayedByInput;
  murderers?: PlayedByInput1 | null;
  town?: PlayedByInput1 | null;
  seats?: {
    [k: string]: PlayedByInput1;
  };
}
/**
 * Who plays a Resident: an Agent on a provider's model, (`"scripted"`) a scripted bot, or
 * (`"prober"`) a scripted bot that tries a prompt injection on the others.
 * The default is an Agent on Claude Haiku, on the Host's subscription unless an API key is set.
 */
export interface PlayedByInput {
  provider?: string;
  model?: string;
  effort?: Effort2;
}
/**
 * Who plays a Resident: an Agent on a provider's model, (`"scripted"`) a scripted bot, or
 * (`"prober"`) a scripted bot that tries a prompt injection on the others.
 * The default is an Agent on Claude Haiku, on the Host's subscription unless an API key is set.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "PlayedBy-Input".
 */
export interface PlayedByInput1 {
  provider?: string;
  model?: string;
  effort?: Effort2;
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
 * via the `definition` "GameList".
 */
export interface GameList {
  games: GameSummary[];
}
/**
 * A game at a glance. Its configuration is left out, since its seed would tell every role;
 * full scope reads it from the game's first event.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "GameSummary".
 */
export interface GameSummary {
  id: string;
  status: "running" | "paused" | "finished" | "aborted" | "failed";
  winner: Side | null;
  created_at: string;
  last_seq: number;
  day: number;
  phase: Phase;
  cost_usd: number | null;
  controls: Control[];
}
/**
 * How many of the others' ballots (`followed`) went against someone this Resident had
 * accused that Day, out of all the others' `ballots` on the Days they accused anyone before
 * a Vote. A vote to skip is a ballot that follows nobody.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Influence".
 */
export interface Influence {
  resident: string;
  followed: number;
  ballots: number;
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
 * A Statement accusing someone the speaker trusts, or defending someone they suspect,
 * beside what the speaker privately held about them.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "LieAbout".
 */
export interface LieAbout {
  kind: "accused_trusted" | "defended_suspected";
  seq: number;
  speaker: string;
  said: string;
  belief: Suspicion;
}
/**
 * Who plays each Resident. A seat's own choice wins, then its side's, then everyone's;
 * the narrator follows everyone's.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Lineup-Input".
 */
export interface LineupInput1 {
  everyone?: PlayedByInput;
  murderers?: PlayedByInput1 | null;
  town?: PlayedByInput1 | null;
  seats?: {
    [k: string]: PlayedByInput1;
  };
}
/**
 * Who plays each Resident. A seat's own choice wins, then its side's, then everyone's;
 * the narrator follows everyone's.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Lineup-Output".
 */
export interface Lineup1 {
  everyone: PlayedBy;
  murderers: PlayedBy1 | null;
  town: PlayedBy1 | null;
  seats: {
    [k: string]: PlayedBy1;
  };
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
/**
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Review".
 */
export interface Review {
  turning_points: (TurningEvent | Swing)[];
  lies: (FalseClaim | LieAbout)[];
  influence: Influence[];
}
/**
 * A death or the Sheriff's shot: the event at `seq`.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "TurningEvent".
 */
export interface TurningEvent {
  kind: "event";
  seq: number;
}
/**
 * One reflection (at `seq`) moving a Resident's suspicion of another a long way at once.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "Swing".
 */
export interface Swing {
  kind: "swing";
  seq: number;
  resident: string;
  suspect: string;
  before: number;
  after: number;
}
/**
 * What the setup form may offer: every provider, and every model with a price. A provider
 * with no API key here is refused when a game is started, saying which key it needs.
 *
 * This interface was referenced by `MurderTownProtocol`'s JSON-Schema
 * via the `definition` "SetupChoices".
 */
export interface SetupChoices {
  providers: string[];
  models: string[];
}
