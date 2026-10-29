/**
 * Who an event concerns: the Resident whose decision it records, and the Residents it names.
 * The Mind inspector lists a Resident's decisions by the first; the feed follows a Resident by both.
 *
 * Pure TypeScript: no React, no I/O.
 */
import type { Payload } from "../protocol";

/** The Resident whose decision an event records, or null for events no Resident decided. */
export function decider(payload: Payload): string | null {
  switch (payload.type) {
    case "bid_placed":
    case "last_words_spoken":
    case "reflection_written":
    case "decision_fell_back":
    case "decision_unanswered":
      return payload.resident;
    case "statement_made":
      return payload.speaker;
    case "sheriff_fired":
    case "sheriff_held_fire":
      return payload.sheriff;
    case "den_message_posted":
    case "kill_vote_cast":
      return payload.murderer;
    case "resident_protected":
      return payload.doctor;
    case "resident_investigated":
      return payload.detective;
    case "dusk_intent_chosen":
      return payload.resident;
    case "conversation_message_posted":
      return payload.speaker;
    case "ballot_cast":
      return payload.voter;
    case "game_configured":
    case "game_started":
    case "role_assigned":
    case "phase_started":
    case "vote_resolved":
    case "resident_died":
    case "victim_chosen":
    case "attack_thwarted":
    case "conversation_started":
    case "open_floor_timed_out":
    case "recap_narrated": // the narrator is not a Resident
    case "roles_revealed":
    case "game_ended":
    case "game_aborted":
      return null;
  }
}

/** Every Resident an event is about: whoever decided it, and whomever it names. */
export function involves(payload: Payload): string[] {
  const actor = decider(payload);
  return [...(actor ? [actor] : []), ...named(payload)];
}

/** Whom an event names besides whoever decided it. */
function named(payload: Payload): string[] {
  switch (payload.type) {
    case "statement_made":
      return [...payload.accused, ...payload.defended];
    case "sheriff_fired":
    case "kill_vote_cast":
    case "resident_protected":
    case "resident_investigated":
      return [payload.target];
    case "ballot_cast":
      return payload.target ? [payload.target] : [];
    case "vote_resolved":
      return payload.banished ? [payload.banished] : [];
    case "resident_died":
      return [payload.resident];
    case "den_message_posted":
      return payload.proposed_victim ? [payload.proposed_victim] : [];
    case "victim_chosen":
      return [payload.victim];
    case "attack_thwarted":
      return payload.saved ? [payload.saved] : [];
    case "dusk_intent_chosen":
      return [...payload.partners];
    case "conversation_started":
      return [...payload.residents];
    case "conversation_message_posted":
      return [payload.partner];
    case "roles_revealed": // it tells everyone's role
      return Object.keys(payload.roles);
    case "game_configured":
    case "game_started":
    case "role_assigned":
    case "phase_started":
    case "bid_placed":
    case "open_floor_timed_out":
    case "sheriff_held_fire":
    case "last_words_spoken":
    case "recap_narrated":
    case "reflection_written":
    case "decision_fell_back":
    case "decision_unanswered":
    case "game_ended":
    case "game_aborted":
      return [];
  }
}
