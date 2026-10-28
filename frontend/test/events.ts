import type { Event, Payload } from "../src/protocol";

let lastSeq = 0;

/** An event the whole town saw, numbered after the last one made. */
export function eventOf(payload: Payload): Event {
  lastSeq += 1;
  return {
    seq: lastSeq,
    day: 1,
    phase: "discussion",
    visibility: { scope: "everyone", residents: [] },
    decision_id: null,
    payload,
  };
}
