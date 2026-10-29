import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { eventsInGameFile } from "../src/core/gameFile";
import type { Event, Mind, PayloadOf, Phase, Review } from "../src/protocol";

/** The scripted game the backend records with `mm play --seed 2 --out ../fixtures/scripted-game.ndjson`, chosen because it shows every kind of event, every kind of lie and a swing in suspicion. */
export function recordedGame(): Event[] {
  return eventsInGameFile(readFileSync(resolve(process.cwd(), "../fixtures/scripted-game.ndjson"), "utf-8"));
}

/** How many of `events` have happened once the `nth` Phase named `phase` has started (counting from 1). */
export function countWhen(events: readonly Event[], phase: Phase, nth: number): number {
  const starts = events.flatMap((event, index) =>
    event.payload.type === "phase_started" && event.payload.phase === phase ? [index + 1] : [],
  );
  return starts[nth - 1] ?? 0;
}

/** How many of `events` have happened once `event` has. */
export function countOf(events: readonly Event[], event: Event | undefined): number {
  const index = event ? events.indexOf(event) : -1;
  if (index < 0) throw new Error("Expected an event of the recorded game");
  return index + 1;
}

export function payloadsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events
    .map((event) => event.payload)
    .filter((payload): payload is PayloadOf<T> => payload.type === type);
}

export function eventsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events.filter((event): event is Event & { payload: PayloadOf<T> } => event.payload.type === type);
}

/** The events up to the moment a side wins, just before every role is revealed. */
export function beforeTheReveal(events: readonly Event[]): Event[] {
  return events.slice(0, events.findIndex((event) => event.payload.type === "roles_revealed"));
}

/** Everyone `events` leaves alive, with the role each was secretly assigned. */
export function livingRoles(events: readonly Event[]) {
  const dead = new Set(payloadsOf(events, "resident_died").map((death) => death.resident));
  return payloadsOf(events, "role_assigned").filter(({ resident }) => !dead.has(resident));
}

/** A JSON file the backend writes beside the recorded game. */
function beside<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(process.cwd(), `../fixtures/scripted-game.${name}.json`), "utf-8")) as T;
}

/** The server's mind of each Resident right after each of their reflections (`mm minds`). */
export function recordedMinds(): { seq: number; mind: Omit<Mind, "perceived"> }[] {
  return beside("minds");
}

/** The backend's review of the recorded game, which `mm play --out` writes beside it. */
export function recordedReview(): Review {
  return beside("review");
}
