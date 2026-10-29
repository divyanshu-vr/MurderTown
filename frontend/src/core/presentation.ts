/**
 * How long each kind of event stays on screen before the next one appears, at normal speed,
 * and which ones hold the next until their animation is done. Every event type needs an
 * entry, so the compiler asks for one when a type is added.
 */
import type { Event, Payload, PayloadOf } from "../protocol";

type Dwell<T extends Payload["type"]> = number | ((payload: PayloadOf<T>) => number);

/** Words said: a moment to notice, then a quarter second a word, about reading speed. */
function said({ text }: { text: string }): number {
  const words = text.split(/\s+/).filter(Boolean).length;
  return 1200 + words * 250;
}

const DWELL: { [T in Payload["type"]]: Dwell<T> } = {
  game_configured: 0, // the feed leaves out the setup, role assignments and reflections
  role_assigned: 0,
  reflection_written: 0,
  game_started: 2000,
  phase_started: 2000,
  statement_made: said,
  last_words_spoken: said,
  den_message_posted: said,
  conversation_message_posted: said,
  recap_narrated: said,
  bid_placed: (bid) => (bid.urgency > 0 ? 400 : 0), // the feed leaves out bids to listen
  open_floor_timed_out: 1500,
  sheriff_fired: 2500,
  sheriff_held_fire: 800,
  ballot_cast: 600,
  vote_resolved: 1500,
  resident_died: 2500,
  kill_vote_cast: 800,
  victim_chosen: 1500,
  resident_protected: 1000,
  resident_investigated: 1000,
  attack_thwarted: 2000,
  dusk_intent_chosen: 400,
  conversation_started: 1000,
  decision_fell_back: 600,
  decision_unanswered: 1000,
  roles_revealed: 4000,
  game_ended: 3000,
  game_aborted: 3000,
};

/**
 * The moments a watcher should see play out, so the next event waits for their animation: a death,
 * the Sheriff's shot, a Vote's result and the ending, and at Night the Murderers making for the
 * Den and every Visit, until whoever is going there arrives.
 */
const BLOCKING: ReadonlySet<Payload["type"]> = new Set([
  "sheriff_fired",
  "vote_resolved",
  "resident_died",
  "game_ended",
  "den_message_posted",
  "kill_vote_cast",
  "victim_chosen",
  "resident_protected",
  "resident_investigated",
]);

/** How long an event stays shown before the next one, in milliseconds at normal speed. */
export function dwellOf(event: Event): number {
  // TypeScript cannot tie an entry to its payload's type here; the table's own type checks that
  const dwell = DWELL[event.payload.type] as Dwell<Payload["type"]>;
  return typeof dwell === "number" ? dwell : dwell(event.payload as never);
}

export function blocks(event: Event): boolean {
  return BLOCKING.has(event.payload.type);
}
