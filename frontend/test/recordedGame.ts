import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { Event, PayloadOf } from "../src/protocol";

/** The scripted game the backend records with `mm play --seed 7 --out ../fixtures/scripted-game.ndjson`. */
export function recordedGame(): Event[] {
  const file = resolve(process.cwd(), "../fixtures/scripted-game.ndjson");
  return readFileSync(file, "utf-8")
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as Event);
}

export function payloadsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events
    .map((event) => event.payload)
    .filter((payload): payload is PayloadOf<T> => payload.type === type);
}

export function eventsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events.filter((event): event is Event & { payload: PayloadOf<T> } => event.payload.type === type);
}
