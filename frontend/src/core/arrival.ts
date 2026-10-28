/**
 * What a follower keeps of each event that arrives: the next one in order, never one it
 * already holds. In full scope every sequence number is sent, so a skipped one is a gap,
 * and the follower asks again from the last event it holds. In public scope the town's
 * unseen events are left out, so gaps are expected there.
 */
export type Arrival = "new" | "duplicate" | "gap";

export function accept(lastSeq: number, seq: number, everySeq: boolean): Arrival {
  if (seq <= lastSeq) return "duplicate";
  if (everySeq && seq > lastSeq + 1) return "gap";
  return "new";
}
