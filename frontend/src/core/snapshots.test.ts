/** Seam 3 (unit): scrubbing starts from the view at the latest Phase start, then folds what follows. */
import { describe, expect, it } from "vitest";

import { recordedGame } from "../../test/recordedGame";
import { foldEvents } from "./gameView";
import { snapshotsOf, viewAt } from "./snapshots";

const events = recordedGame();

describe("snapshots of a game", () => {
  it("plus the events after them give the same view as folding everything, at every point", () => {
    const snapshots = snapshotsOf(events);

    for (let count = 0; count <= events.length; count++) {
      expect(viewAt(events, snapshots, count)).toEqual(foldEvents(events.slice(0, count)));
    }
  });
});
