import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { eventsInGameFile } from "../src/core/gameFile";
import type { Event, Mind, PayloadOf } from "../src/protocol";

/** The scripted game the backend records with `mm play --seed 1 --out ../fixtures/scripted-game.ndjson`, chosen because it shows every kind of event. */
export function recordedGame(): Event[] {
  return eventsInGameFile(readFileSync(resolve(process.cwd(), "../fixtures/scripted-game.ndjson"), "utf-8"));
}

export function payloadsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events
    .map((event) => event.payload)
    .filter((payload): payload is PayloadOf<T> => payload.type === type);
}

export function eventsOf<T extends Event["payload"]["type"]>(events: readonly Event[], type: T) {
  return events.filter((event): event is Event & { payload: PayloadOf<T> } => event.payload.type === type);
}

/** The server's mind of each Resident right after each of their reflections (`mm minds`). */
export function recordedMinds(): { seq: number; mind: Omit<Mind, "perceived"> }[] {
  const file = resolve(process.cwd(), "../fixtures/scripted-game.minds.json");
  return JSON.parse(readFileSync(file, "utf-8")) as { seq: number; mind: Omit<Mind, "perceived"> }[];
}
