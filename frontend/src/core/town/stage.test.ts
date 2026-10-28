/** Seam 3 (unit): what is said and voted on stage, from the recorded game. */
import { describe, expect, it } from "vitest";

import { present } from "../../../test/present";
import { eventsOf, recordedGame } from "../../../test/recordedGame";
import type { Event } from "../../protocol";
import { stageOf } from "./stage";

const events = recordedGame();
const stageAt = ({ seq }: Event) => stageOf(events.filter((event) => event.seq <= seq));
const nextPhaseAfter = ({ seq }: Event) =>
  present(events.find((event) => event.seq > seq && event.payload.type === "phase_started"), "a later Phase");
const [firstStatement, secondStatement] = eventsOf(events, "statement_made");
const lastWords = present(eventsOf(events, "last_words_spoken")[0], "last words");
const resolved = present(eventsOf(events, "vote_resolved")[0], "a resolved Vote");

describe("what is on stage", () => {
  it("shows the latest words said until someone else speaks or the Phase ends", () => {
    const first = present(firstStatement, "a Statement");
    const second = present(secondStatement, "a second Statement");

    expect(stageAt(first).words).toEqual({ seq: first.seq, speaker: first.payload.speaker, text: first.payload.text });
    expect(stageAt(second).words?.speaker).toBe(second.payload.speaker);
    expect(stageAt(nextPhaseAfter(first)).words).toBeNull();
  });

  it("gives the banished their last words", () => {
    expect(stageAt(lastWords).words).toMatchObject({ speaker: lastWords.payload.resident, text: lastWords.payload.text });
  });

  it("draws each ballot cast so far in the Vote, counting them up to the Vote's own tally", () => {
    const ballots = eventsOf(events, "ballot_cast").filter((ballot) => ballot.seq < resolved.seq);
    const againstSomeone = present(ballots.find((ballot) => ballot.payload.target !== null), "a ballot against someone");
    const target = present(againstSomeone.payload.target, "a target");

    const early = stageAt(againstSomeone);
    expect(early.ballots.at(-1)).toEqual({ voter: againstSomeone.payload.voter, target });
    expect(early.counts.get(target)).toBe(1);

    const atTheEnd = stageAt(resolved);
    expect(Object.fromEntries(atTheEnd.counts)).toEqual(resolved.payload.tally);
    expect(atTheEnd.ballots).toHaveLength(ballots.length - resolved.payload.skips);
  });

  it("clears the ballots once the Vote is over", () => {
    expect(stageAt(nextPhaseAfter(resolved)).ballots).toEqual([]);
  });
});
