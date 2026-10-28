/**
 * Where everyone stands in town for a view. A pure function of the view, so seeking lands
 * exactly where playing on would have: the town walks Residents from one layout to the next,
 * and snaps to it when the view jumps.
 *
 * In Discussion, the Showdown and the Vote, and once the game has ended, the living stand in a
 * semicircle behind the well, by seat, facing it. Before the game, at Dawn, at Dusk and at Night
 * they are at their own door (where Dusk and Night take them is still to come). The dead stay
 * where they died: in the square if banished or shot, at their door if murdered at Night.
 */
import type { Phase } from "../../protocol";
import type { GameView } from "../gameView";
import type { Tile } from "./path";
import type { TownPlan } from "./plan";

export type Facing = "left" | "right";

/** A spot in town, in tiles: tile (x, y) runs from (x, y) to (x + 1, y + 1). */
export interface Point {
  x: number;
  y: number;
}

export interface Placement {
  name: string;
  seat: number;
  at: Point;
  facing: Facing;
  dead: boolean;
}

/** The Phases the living spend in the square; the rest of the time they are at home. */
export const IN_THE_SQUARE: ReadonlySet<Phase> = new Set(["discussion", "showdown", "vote", "ended"]);

/** How finely the semicircle is measured to space everyone evenly along it. */
const SAMPLES = 720;

export function layoutFor(view: GameView, plan: TownPlan): Placement[] {
  const spots = semicircle(plan, view.residents.length);
  const centre = middleOf(plan.well);
  return view.residents.map(({ name, seat, fate }) => {
    const inTheSquare = fate ? fate !== "murdered" : IN_THE_SQUARE.has(view.phase);
    const at = (inTheSquare ? spots[seat] : undefined) ?? middleOf(plan.doors[seat] ?? plan.hall);
    const facing = inTheSquare && at.x > centre.x ? "left" : "right";
    return { name, seat, at, facing, dead: fate !== null };
  });
}

export function middleOf({ x, y }: Tile): Point {
  return { x: x + 0.5, y: y + 0.5 };
}

/** `count` spots evenly spaced along half an ellipse behind the well, west to east, a tile in from the square's sides and top. */
function semicircle(plan: TownPlan, count: number): Point[] {
  const centre = middleOf(plan.well);
  const across = plan.square.width / 2 - 1;
  const up = centre.y - plan.square.y - 1;
  const samples = Array.from({ length: SAMPLES + 1 }, (_, index) => {
    const angle = Math.PI * (1 - index / SAMPLES);
    return { x: centre.x + across * Math.cos(angle), y: centre.y - up * Math.sin(angle) };
  });
  const lengths = samples.reduce<number[]>((walked, sample, index) => {
    const previous = samples[index - 1] ?? sample;
    walked.push((walked.at(-1) ?? 0) + Math.hypot(sample.x - previous.x, sample.y - previous.y));
    return walked;
  }, []);
  const total = lengths.at(-1) ?? 0;
  return Array.from({ length: count }, (_, spot) => {
    const wanted = count > 1 ? (total * spot) / (count - 1) : total / 2;
    return samples[lengths.findIndex((length) => length >= wanted - 1e-9)] ?? centre;
  });
}
