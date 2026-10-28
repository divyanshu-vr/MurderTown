/**
 * What the camera frames when following the action and no moment is playing: the semicircle
 * while the town gathers in the square; at Night, the house visited last, or the Den while the
 * Murderers meet there; otherwise the whole town. (A moment, such as a fall or the Sheriff's shot,
 * frames its own place: see `areaAround`.)
 */
import type { GameView } from "../gameView";
import { IN_THE_SQUARE, middleOf, type Point } from "./layout";
import type { Area, TownPlan } from "./plan";
import type { Stage } from "./stage";

export function focusOf(view: GameView, stage: Stage, plan: TownPlan): Area {
  const { square, well, doors, den } = plan;
  if (IN_THE_SQUARE.has(view.phase)) {
    // the semicircle, with room above it for what is said and below it for the well
    const top = square.y - 2;
    return { x: square.x - 1, y: top, width: square.width + 2, height: well.y + 3 - top };
  }
  if (view.phase === "night") {
    const visited = stage.visits.at(-1)?.target;
    const seat = view.residents.find(({ name }) => name === visited)?.seat;
    const door = seat === undefined ? undefined : doors[seat];
    if (door) return areaAround(middleOf(door));
    if (stage.den.length) return areaAround(middleOf(den));
  }
  return { x: 0, y: 0, width: plan.grid.width, height: plan.grid.height };
}

/** Twelve by eight tiles round a spot: close enough to see who is there, wide enough to see them arrive. */
export function areaAround(at: Point): Area {
  return { x: at.x - 6, y: at.y - 4.5, width: 12, height: 8 };
}
