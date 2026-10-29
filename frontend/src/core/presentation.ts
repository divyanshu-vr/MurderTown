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

/** How fast words appear, in the town's bubbles and the feed: characters a second of game time. */
export const TYPING_PER_SECOND = 45;

/** Words said aloud, which type out as they appear. */
const SPOKEN: ReadonlySet<Payload["type"]> = new Set([
  "statement_made",
  "last_words_spoken",
  "den_message_posted",
  "conversation_message_posted",
  "recap_narrated",
]);

export function typesOut(event: Event): boolean {
  return SPOKEN.has(event.payload.type);
}

/** How many characters of words have typed out after `gameMs` more, from `typed`. */
export function typedAfter(typed: number, gameMs: number, length: number): number {
  return Math.min(length, typed + (gameMs * TYPING_PER_SECOND) / 1000);
}

/** How long a Turn's raised hands show, once its Bids are all in, before the Statement. */
export const HANDS_UP_MS = 1200;

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
  bid_placed: HANDS_UP_MS, // a Turn's Bids appear together: see dwellOf
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
 * Den and every Visit, until its visitors are home again.
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

/** A Bid, or the note that one fell back: what a Turn's raised hands are made of. */
function inTheBids({ payload }: Event): boolean {
  return payload.type === "bid_placed" || (payload.type === "decision_fell_back" && payload.kind === "bid");
}

/**
 * How long an event stays shown before the next one, in milliseconds at normal speed. A Bid
 * (or a note that one fell back) followed by another shows for no time, so a Turn's Bids (and
 * those of any quiet Turns before it, all to listen) appear together; the last of them shows
 * as long as the raised hands do.
 */
export function dwellOf(event: Event, next?: Event): number {
  if (inTheBids(event)) return next && inTheBids(next) ? 0 : HANDS_UP_MS;
  // TypeScript cannot tie an entry to its payload's type here; the table's own type checks that
  const dwell = DWELL[event.payload.type] as Dwell<Payload["type"]>;
  return typeof dwell === "number" ? dwell : dwell(event.payload as never);
}

export function blocks(event: Event): boolean {
  return BLOCKING.has(event.payload.type);
}
