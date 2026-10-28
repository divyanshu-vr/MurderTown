/**
 * A game file: a game's whole log, one event per line, as `mm export` and `mm play --out`
 * write it. It holds everything the console needs to replay the game with no server.
 */
import type { Event } from "../protocol";

export function eventsInGameFile(text: string): Event[] {
  return text
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as Event);
}
