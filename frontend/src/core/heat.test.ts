/** Seam 3 (unit): the heatmap, folded from the recorded game, against the server's own folds. */
import { describe, expect, it } from "vitest";

import { recordedGame, recordedMinds, recordedReview } from "../../test/recordedGame";
import { heatAt } from "./heat";

const events = recordedGame();
const minds = recordedMinds();
/** How many events have happened once each Phase has started. */
const phaseStarts = events.flatMap((event, index) => (event.payload.type === "phase_started" ? [index + 1] : []));

type Levels = Map<string, Map<string, number>>;

/** Each Resident's Suspicions as the server's mind of them stood just before `seq`. */
function serverLevelsBefore(seq: number): Levels {
  const latest: Levels = new Map();
  for (const { seq: at, mind } of minds) {
    if (at >= seq) continue;
    latest.set(mind.resident, new Map(mind.memory.dossier.map((s) => [s.resident, s.suspicion])));
  }
  return latest;
}

function levelsAt(count: number): Levels {
  const heat = heatAt(events.slice(0, count));
  return new Map(
    [...(heat?.suspicions ?? new Map())].map(([resident, row]) => [
      resident,
      new Map([...row].map(([suspect, cell]) => [suspect, cell.suspicion])),
    ]),
  );
}

describe("the suspicion heatmap", () => {
  it("shows each Resident's dossier as it stood at the start of the Phase reached", () => {
    for (const count of phaseStarts) {
      const seq = events[count - 1]?.seq ?? 0;
      const levels = levelsAt(count);
      for (const [resident, row] of serverLevelsBefore(seq)) expect(levels.get(resident)).toEqual(row);
    }
  });

  it("shows nothing from later in a Phase than its start, though Residents reflect during it", () => {
    const start = phaseStarts.find((count, i) => {
      const end = phaseStarts[i + 1] ?? events.length;
      return events.slice(count, end).some((event) => event.payload.type === "reflection_written");
    });
    if (start === undefined) throw new Error("The recorded game has no reflection inside a Phase");
    const end = phaseStarts[phaseStarts.indexOf(start) + 1] ?? events.length;

    expect(levelsAt(end - 1)).toEqual(levelsAt(start));
    expect(levelsAt(end)).not.toEqual(levelsAt(start));
  });

  it("gives each Suspicion's change since the last Phase start at which one was different", () => {
    const startAfter = (seq: number) => phaseStarts.find((count) => (events[count - 1]?.seq ?? 0) > seq);
    const swing = recordedReview().turning_points.find((point) => point.kind === "swing" && startAfter(point.seq));
    if (swing?.kind !== "swing") throw new Error("The recorded game has no swing in suspicion before a Phase start");

    const heat = heatAt(events.slice(0, startAfter(swing.seq)));

    expect(heat?.suspicions.get(swing.resident)?.get(swing.suspect)).toMatchObject({
      suspicion: swing.after,
      change: swing.after - swing.before,
    });
    expect(heat?.since).not.toBeNull();
  });

  it("has nothing to show before the first Phase", () => {
    expect(heatAt(events.slice(0, 1))).toBeNull();
  });
});
