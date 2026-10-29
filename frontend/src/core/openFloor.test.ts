/** Seam 3 (unit): how long until the Vote, as of the events shown, in the recorded game. */
import { describe, expect, it } from "vitest";

import { firstOnTheFloor, lastOpening, readAt, shownAgo, timedGame, upTo } from "../../test/openFloor";
import { present } from "../../test/present";
import { eventsOf, recordedGame } from "../../test/recordedGame";
import { openFloorOf } from "./openFloor";
import { dwellOf } from "./presentation";

const events = recordedGame();

describe("the countdown to the Vote", () => {
  it("has nothing to count before the Opening round is over, nor once the Discussion is", () => {
    const opening = present(eventsOf(events, "statement_made")[0], "the first Statement");
    expect(openFloorOf(upTo(events, opening))).toBeNull();
    const showdown = present(
      eventsOf(events, "phase_started").find(({ seq, payload }) => seq > firstOnTheFloor.seq && payload.phase === "showdown"),
      "the Showdown",
    );
    expect(openFloorOf(upTo(events, showdown))).toBeNull();
  });

  it("counts the Statements left before the Vote, with no time to count in a game without a limit", () => {
    expect(openFloorOf(upTo(events, lastOpening))).toEqual({ statementsLeft: 8, secondsLeft: null });
    expect(openFloorOf(upTo(events, firstOnTheFloor))).toEqual({ statementsLeft: 7, secondsLeft: null });
  });

  it("follows the server's clock as the latest Statement on the Open floor read it, then counts on from there", () => {
    const shown = upTo(readAt(timedGame(180), firstOnTheFloor, 150), firstOnTheFloor);

    expect(openFloorOf(shown)?.secondsLeft).toBe(150);
    expect(openFloorOf(shown, shownAgo(4000, firstOnTheFloor))?.secondsLeft).toBe(146);
    expect(openFloorOf(shown, shownAgo(4000, lastOpening))?.secondsLeft).toBe(150);
  });

  it("counts the limit down from when the Opening round's last Statement was shown, before a Statement reads the clock", () => {
    const shown = upTo(timedGame(180), firstOnTheFloor);

    expect(openFloorOf(upTo(timedGame(180), lastOpening))?.secondsLeft).toBe(180);
    expect(openFloorOf(shown, shownAgo(41_000, lastOpening))?.secondsLeft).toBe(139);
    expect(openFloorOf(shown, shownAgo(10 * 60_000, lastOpening))?.secondsLeft).toBe(0);
  });

  it("reckons the time on screen of events jumped over from how long each is shown", () => {
    const shown = upTo(timedGame(180), firstOnTheFloor);
    const jumpedOver = shown.filter(({ seq }) => seq >= lastOpening.seq);
    const reckoned = jumpedOver.slice(0, -1).reduce((ms, event, i) => ms + dwellOf(event, jumpedOver[i + 1]), 0);

    expect(openFloorOf(shown, shownAgo(2000, firstOnTheFloor))?.secondsLeft).toBeCloseTo(180 - (reckoned + 2000) / 1000);
  });
});
