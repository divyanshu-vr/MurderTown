/**
 * A Resident walking from one spot to another: the fewest tiles there, through the middle of
 * each, then the last stretch to the exact spot, at four tiles a second of game time (so faster
 * or slower with playback, and not at all while it holds: see clock.ts).
 */
import { type Facing, middleOf, type Point } from "./layout";
import { type Grid, pathBetween } from "./path";

export const TILES_PER_SECOND = 4;

/** A straight stretch of the walk, starting `start` tiles into it. */
interface Leg {
  from: Point;
  to: Point;
  start: number;
  length: number;
}

export class Walk {
  /** Which way the Resident faces, once they have taken a step sideways. */
  facing: Facing | null = null;
  private readonly legs: Leg[];
  private readonly end: Point;
  private readonly length: number;
  /** How far along the walk is, in tiles. */
  private walked = 0;

  constructor(from: Point, to: Point, grid: Grid) {
    const way = pathBetween(grid, tileOf(from), tileOf(to)) ?? [];
    const corners = [from, ...way.slice(0, -1).map(middleOf), to];
    let start = 0;
    this.legs = corners.slice(1).map((end, index) => {
      const begin = corners[index] ?? end;
      const leg = { from: begin, to: end, start, length: Math.hypot(end.x - begin.x, end.y - begin.y) };
      start += leg.length;
      return leg;
    });
    this.end = to;
    this.length = start;
  }

  get arrived(): boolean {
    return this.walked >= this.length;
  }

  /** Where the walk has got to. */
  get at(): Point {
    const leg = this.legUnderway();
    if (!leg) return this.end;
    const along = (this.walked - leg.start) / leg.length;
    return { x: leg.from.x + (leg.to.x - leg.from.x) * along, y: leg.from.y + (leg.to.y - leg.from.y) * along };
  }

  /** Walk on for `gameMs` of game time. */
  advance(gameMs: number): void {
    this.walked = Math.min(this.length, this.walked + (gameMs * TILES_PER_SECOND) / 1000);
    const leg = this.legUnderway();
    if (leg && leg.to.x !== leg.from.x) this.facing = leg.to.x < leg.from.x ? "left" : "right";
  }

  /** The stretch being walked, or none once arrived. */
  private legUnderway(): Leg | undefined {
    return this.legs.find((leg) => this.walked < leg.start + leg.length);
  }
}

function tileOf({ x, y }: Point) {
  return { x: Math.floor(x), y: Math.floor(y) };
}
