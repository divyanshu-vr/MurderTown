/** Seam 3: the console's fold of a Resident's mind agrees with the server's, at every recorded change. */
import { describe, expect, it } from "vitest";

import { recordedGame, recordedMinds } from "../../test/recordedGame";
import { mindOf } from "./mind";

describe("the console's fold of a mind", () => {
  it("matches the server's mind right after every reflection in the recorded game", () => {
    const events = recordedGame();
    const minds = recordedMinds();
    expect(minds.length).toBeGreaterThan(50);

    for (const { seq, mind } of minds) {
      const folded = mindOf(
        events.filter((event) => event.seq <= seq),
        mind.resident,
      );
      expect(folded && { ...folded, decisions: undefined }).toEqual({ ...mind, decisions: undefined });
    }
  });
});
