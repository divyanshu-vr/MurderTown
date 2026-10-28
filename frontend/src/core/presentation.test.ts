/** Seam 3 (unit): how long each event stays on screen before the next one appears, at normal speed. */
import { describe, expect, it } from "vitest";

import { eventOf as event } from "../../test/events";
import type { Event } from "../protocol";
import { blocks, dwellOf } from "./presentation";

function statement(text: string): Event {
  return event({
    type: "statement_made",
    speaker: "Ava",
    text,
    part: "opening_round",
    addressed: [],
    accused: [],
    defended: [],
    claimed_role: null,
  });
}

describe("how long an event is shown", () => {
  it("gives what is said a moment, then a quarter second a word, so it can be read", () => {
    expect(dwellOf(statement("I saw Bram near the well last night."))).toBe(1200 + 8 * 250);
    expect(dwellOf(statement("No."))).toBe(1200 + 250);
  });

  it("gives what the feed leaves out no time at all", () => {
    expect(dwellOf(event({ type: "bid_placed", resident: "Ava", urgency: 0, reason: "listening" }))).toBe(0);
    expect(dwellOf(event({ type: "reflection_written", resident: "Ava", journal_entry: "", notebook: "", suspicions: [] }))).toBe(
      0,
    );
  });

  it("counts a death among the moments that wait for their animation", () => {
    const died = event({ type: "resident_died", resident: "Ava", cause: "banished", role: "civilian" });

    expect(blocks(died)).toBe(true);
    expect(blocks(statement("Hello."))).toBe(false);
  });
});
