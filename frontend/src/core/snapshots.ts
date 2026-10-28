/**
 * The view at any point of a game, for scrubbing: start from the view at the latest Phase
 * start before that point, then fold only the events after it.
 */
import type { Event } from "../protocol";
import { applyEvent, emptyView, type GameView } from "./gameView";

/** The view once the first `count` events have happened. */
export interface Snapshot {
  count: number;
  view: GameView;
}

/** The view before anything happens, and at each Phase start. */
export function snapshotsOf(events: readonly Event[]): Snapshot[] {
  const snapshots: Snapshot[] = [{ count: 0, view: emptyView }];
  let view = emptyView;
  events.forEach((event, index) => {
    view = applyEvent(view, event);
    if (event.payload.type === "phase_started") snapshots.push({ count: index + 1, view });
  });
  return snapshots;
}

/** The view once the first `count` events have happened. */
export function viewAt(events: readonly Event[], snapshots: readonly Snapshot[], count: number): GameView {
  const start = snapshots.findLast((snapshot) => snapshot.count <= count) ?? { count: 0, view: emptyView };
  return events.slice(start.count, count).reduce(applyEvent, start.view);
}
