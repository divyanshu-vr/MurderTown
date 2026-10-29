/** Seam 3 (unit): the feed's words for a Statement, in the recorded game and a Replay-site game. */
import { describe, expect, it } from "vitest";

import { present } from "../../test/present";
import { eventsOf, recordedGame, siteGame } from "../../test/recordedGame";
import { describeEvent } from "./describeEvent";

describe("a Statement in the feed", () => {
  it("names whom it asks to answer", () => {
    const asking = present(
      eventsOf(recordedGame(), "statement_made").find(({ payload }) => payload.asked),
      "a Statement that asks someone",
    );

    expect(describeEvent(asking)).toBe(`${asking.payload.speaker}: "${asking.payload.text}" (asks ${asking.payload.asked} to answer)`);
  });

  it("reads a game recorded before Statements could ask, as words alone", () => {
    const statement = present(eventsOf(siteGame("never-wrong"), "statement_made")[0], "a Statement");

    expect(describeEvent(statement)).toBe(`${statement.payload.speaker}: "${statement.payload.text}"`);
  });
});
