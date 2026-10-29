import type { Event } from "../src/protocol";
import { present } from "./present";
import { eventsOf, recordedGame } from "./recordedGame";

/** The recorded game as if its Open floors had a time limit of `seconds`: it was played without one. */
export function timedGame(seconds: number): Event[] {
  return recordedGame().map((event) =>
    event.payload.type === "game_started"
      ? { ...event, payload: { ...event.payload, rules: { ...event.payload.rules, open_floor_seconds: seconds } } }
      : event,
  );
}

const statements = eventsOf(recordedGame(), "statement_made");

/** The recorded game's first Statement on an Open floor. */
export const firstOnTheFloor = present(
  statements.find(({ payload }) => payload.part === "open_floor"),
  "an Open-floor Statement",
);

/** The Opening round's last Statement before it, when that Open floor's clock starts. */
export const lastOpening = present(
  statements.findLast(({ seq, payload }) => payload.part === "opening_round" && seq < firstOnTheFloor.seq),
  "the Opening round's last Statement",
);

/** `events` as if the server's clock had `secondsLeft` on the Open floor when `statement` was made. */
export function readAt(events: readonly Event[], statement: Event, secondsLeft: number): Event[] {
  return events.map((event) =>
    event.seq === statement.seq && event.payload.type === "statement_made"
      ? { ...event, payload: { ...event.payload, seconds_left: secondsLeft } }
      : event,
  );
}

/** Playback that showed `event` `ms` ago, and no other event since it last jumped. */
export function shownAgo(ms: number, event: Event) {
  return (seq: number) => (seq === event.seq ? ms : null);
}

/** `events` up to and including `event`. */
export function upTo(events: readonly Event[], { seq }: Event): Event[] {
  return events.filter((event) => event.seq <= seq);
}
