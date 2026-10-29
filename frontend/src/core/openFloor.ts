/**
 * How long until the Vote, for the phase bar. The Open floor ends at its Statement cap, at its
 * time limit, or after two quiet Turns. The server starts its clock once the Opening round's last
 * Statement is made, and each Statement on the floor records how long it had left, so live and
 * replayed games show the same time at every Statement. From there the countdown runs on for as
 * long as playback has shown what followed: watching live, that includes the waits for the
 * server; an event playback jumped over counts for as long as it is shown. A game without a time
 * limit counts only Statements.
 */
import type { Event } from "../protocol";
import type { SinceShown } from "./playback";
import { dwellOf } from "./presentation";

export interface OpenFloorClock {
  statementsLeft: number;
  /** Seconds until the time limit; null when the Open floor has none. */
  secondsLeft: number | null;
}

/** Where the Open floor stands as of `events` shown; null outside one. */
export function openFloorOf(events: readonly Event[], sinceShown: SinceShown = () => null): OpenFloorClock | null {
  const start = events.findLastIndex(({ payload }) => payload.type === "phase_started");
  const phase = events[start]?.payload;
  const started = events.find(({ payload }) => payload.type === "game_started")?.payload;
  if (phase?.type !== "phase_started" || phase.phase !== "discussion" || started?.type !== "game_started") return null;

  const before = events.slice(0, start);
  const speakers = started.residents.length - before.filter(({ payload }) => payload.type === "resident_died").length;
  const discussion = events.slice(start + 1);
  const opening = discussion.filter(({ payload }) => payload.type === "statement_made" && payload.part === "opening_round");
  const lastOpening = opening.at(-1);
  if (!lastOpening || opening.length < speakers) return null; // the Open floor has not begun

  const onTheFloor = discussion.filter(({ payload }) => payload.type === "statement_made" && payload.part === "open_floor");
  const statementsLeft = Math.max(0, started.rules.open_floor_statements - onTheFloor.length);
  const limit = started.rules.open_floor_seconds;
  if (limit === null) return { statementsLeft, secondsLeft: null };
  if (discussion.some(({ payload }) => payload.type === "open_floor_timed_out")) return { statementsLeft, secondsLeft: 0 };

  const reading = lastReading(onTheFloor) ?? { from: lastOpening, secondsLeft: limit };
  const passedMs = timeOnScreen(discussion.slice(discussion.indexOf(reading.from)), sinceShown);
  return { statementsLeft, secondsLeft: Math.max(0, reading.secondsLeft - passedMs / 1000) };
}

/** The latest Statement on the floor that recorded how long the server's clock had left; games
 * recorded before Statements did have none. */
function lastReading(onTheFloor: readonly Event[]): { from: Event; secondsLeft: number } | null {
  for (const from of onTheFloor.toReversed()) {
    const said = from.payload;
    if (said.type === "statement_made" && typeof said.seconds_left === "number") return { from, secondsLeft: said.seconds_left };
  }
  return null;
}

/** How long since the first of `events` was shown: the time each is shown for, up to the first
 * that playback showed, then how long ago that was. */
function timeOnScreen(events: readonly Event[], sinceShown: SinceShown): number {
  let ms = 0;
  for (const [i, event] of events.entries()) {
    const since = sinceShown(event.seq);
    if (since !== null) return ms + since;
    const next = events[i + 1];
    if (next) ms += dwellOf(event, next);
  }
  return ms;
}
