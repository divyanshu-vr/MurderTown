/**
 * What is happening on stage as of the events shown, for the town to draw over the layout:
 * the latest words said this Phase, and the ballots cast so far in a Vote. Both start afresh
 * with each Phase.
 */
import type { Event } from "../../protocol";

/** Words said aloud: a Statement or Last words. */
export interface Words {
  seq: number;
  speaker: string;
  text: string;
}

export interface Ballot {
  voter: string;
  target: string;
}

export interface Stage {
  /** The latest words said this Phase. */
  words: Words | null;
  /** The ballots against someone so far this Phase, in the order cast; a vote to skip draws nothing. */
  ballots: Ballot[];
  /** How many ballots each Resident has against them so far. */
  counts: Map<string, number>;
}

export function stageOf(events: readonly Event[]): Stage {
  const start = events.findLastIndex((event) => event.payload.type === "phase_started");
  const stage: Stage = { words: null, ballots: [], counts: new Map() };
  for (const { seq, payload } of events.slice(start + 1)) {
    if (payload.type === "statement_made") stage.words = { seq, speaker: payload.speaker, text: payload.text };
    if (payload.type === "last_words_spoken") stage.words = { seq, speaker: payload.resident, text: payload.text };
    if (payload.type === "ballot_cast" && payload.target !== null) {
      stage.ballots.push({ voter: payload.voter, target: payload.target });
      stage.counts.set(payload.target, (stage.counts.get(payload.target) ?? 0) + 1);
    }
  }
  return stage;
}
