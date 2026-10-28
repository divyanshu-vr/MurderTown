/**
 * Where everyone stands in town for a view and what is on stage. A pure function of the two, so
 * seeking lands exactly where playing on would have: the town walks Residents from one layout to
 * the next, and snaps to it when the view jumps.
 *
 * - In Discussion, the Showdown and the Vote, and once the game has ended, the living stand in a
 *   semicircle behind the well, by seat, facing it.
 * - At Dusk, each pair talking stands side by side about halfway between their homes, facing each
 *   other; those doing a Chore go to a chore spot, facing their work; everyone else wanders from
 *   spot to spot as Dusk goes by.
 * - At Night everyone is at home, except that the Murderers meet at the Den and then go to their
 *   Victim's house, as the Doctor and the Detective go to the houses of whom they chose (a Doctor
 *   protecting themselves stays in). Mystery mode sees none of that, so it sees everyone at home.
 * - Before the game and at Dawn, everyone is at home.
 * - The dead stay where they died: in the square if banished or shot, at their door if murdered.
 *
 * Away from the semicircle, everyone has a tile of their own, claimed in a fixed order (homes,
 * graves and lanterns; then pairs, Chores and wanderers, or the Den and the visitors in the order
 * they set out), so the same view always gives the same layout.
 */
import type { Phase } from "../../protocol";
import type { GameView, ResidentView } from "../gameView";
import type { Grid, Tile } from "./path";
import type { TownPlan } from "./plan";
import type { Stage } from "./stage";

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
  atChore: boolean;
}

/** How a Resident stands: where, which way, and whether at a Chore. */
type Pose = Pick<Placement, "at" | "facing" | "atChore">;

/** The Phases the living spend in the square. */
export const IN_THE_SQUARE: ReadonlySet<Phase> = new Set(["discussion", "showdown", "vote", "ended"]);

/** How finely the semicircle is measured to space everyone evenly along it. */
const SAMPLES = 720;

/**
 * Spreading the town over the chore and wander spots: each seat starts looking seven spots on
 * from the seat before, every Day shifts everyone three spots, and each wanderer moves on to their
 * next spot every six events of Dusk, two events later than the seat before so they do not all
 * set off at once.
 */
const SPREAD = { bySeat: 7, byDay: 3, wanderEvery: 6, wanderLaterBySeat: 2 };

export function layoutFor(view: GameView, stage: Stage, plan: TownPlan): Placement[] {
  const town = new Placing(view.residents, plan);
  if (IN_THE_SQUARE.has(view.phase)) town.inTheSquare();
  else if (view.phase === "dusk") town.atDusk(view.day, stage);
  else if (view.phase === "night") town.atNight(stage);
  return town.placements();
}

export function middleOf({ x, y }: Tile): Point {
  return { x: x + 0.5, y: y + 0.5 };
}

/** Placing everyone for one layout: their homes, graves and the lanterns first, then whatever the Phase calls for. */
class Placing {
  private readonly tiles: Tiles;
  private readonly poses = new Map<string, Pose>();
  private readonly seatOf: Map<string, number>;
  private readonly semicircle: Point[];
  private readonly living: readonly ResidentView[];

  constructor(
    private readonly residents: readonly ResidentView[],
    private readonly plan: TownPlan,
  ) {
    this.tiles = new Tiles(plan.grid);
    this.semicircle = semicircleOf(plan, residents.length);
    this.living = residents.filter(({ fate }) => fate === null);
    this.seatOf = new Map(this.living.map(({ name, seat }) => [name, seat]));
    for (const lantern of plan.lanterns) this.tiles.claim(middleOf(lantern));
    for (const { seat } of residents) this.tiles.claim(this.home(seat));
    for (const { name, seat, fate } of residents) {
      if (!fate) continue;
      const at = fate === "murdered" ? this.home(seat) : (this.semicircle[seat] ?? this.home(seat));
      this.tiles.claim(at);
      this.poses.set(name, standing(at));
    }
  }

  inTheSquare(): void {
    const well = middleOf(this.plan.well);
    for (const { name, seat } of this.living) {
      const at = this.semicircle[seat] ?? this.home(seat);
      this.poses.set(name, standing(at, at.x > well.x ? "left" : "right"));
    }
  }

  /** Pairs halfway between their homes, then Chores at chore spots, then everyone else wandering. */
  atDusk(day: number, stage: Stage): void {
    const spots = new Set([...this.plan.chores, ...this.plan.wanders].map(keyOf));
    for (const pair of stage.pairs) {
      const [seatA, seatB] = [this.seatOf.get(pair[0]), this.seatOf.get(pair[1])];
      if (seatA === undefined || seatB === undefined) continue;
      const [homeA, homeB] = [this.home(seatA), this.home(seatB)];
      const halfway = { x: (homeA.x + homeB.x) / 2, y: (homeA.y + homeB.y) / 2 };
      const offTheSpots = (tile: Tile) => !spots.has(keyOf(tile));
      const left = this.tiles.nearest(halfway, ({ x, y }) => {
        const right = { x: x + 1, y };
        return offTheSpots({ x, y }) && offTheSpots(right) && this.tiles.free(right);
      });
      if (!left) continue;
      const right = { x: left.x + 1, y: left.y };
      this.tiles.claim(right);
      const [westerner, easterner] = homeA.x <= homeB.x ? pair : [pair[1], pair[0]];
      this.poses.set(westerner, standing(left, "right"));
      this.poses.set(easterner, standing(right, "left"));
    }
    const firstSpot = (seat: number) => seat * SPREAD.bySeat + day * SPREAD.byDay;
    for (const { name, seat } of this.unplaced()) {
      if (stage.activities.get(name) !== "chore") continue;
      const at = this.tiles.firstFree(this.plan.chores, firstSpot(seat));
      if (at) this.poses.set(name, { at, facing: this.facingTheWork(at), atChore: true });
    }
    for (const { name, seat } of this.unplaced()) {
      const moves = Math.floor((stage.eventsThisPhase + seat * SPREAD.wanderLaterBySeat) / SPREAD.wanderEvery);
      const at = this.tiles.firstFree(this.plan.wanders, firstSpot(seat) + moves) ?? this.tiles.nearest(this.home(seat));
      if (at) this.poses.set(name, standing(at));
    }
  }

  /** The Murderers at the Den, then every visitor at the house they went to; everyone else at home. */
  atNight(stage: Stage): void {
    const den = middleOf(this.plan.den);
    for (const murderer of stage.den) {
      const at = this.seatOf.has(murderer) ? this.tiles.nearest(den) : null;
      if (at) this.poses.set(murderer, standing(at, facingTowards(at, den)));
    }
    for (const { visitor, target } of stage.visits) {
      const [visitorSeat, targetSeat] = [this.seatOf.get(visitor), this.seatOf.get(target)];
      if (visitorSeat === undefined || targetSeat === undefined || visitor === target) continue;
      const door = this.home(targetSeat);
      const at = this.tiles.nearest(door);
      if (at) this.poses.set(visitor, standing(at, facingTowards(at, door)));
    }
  }

  placements(): Placement[] {
    return this.residents.map(({ name, seat, fate }) => ({
      name,
      seat,
      dead: fate !== null,
      ...(this.poses.get(name) ?? standing(this.home(seat))),
    }));
  }

  private home(seat: number): Point {
    return middleOf(this.plan.doors[seat] ?? this.plan.hall);
  }

  private unplaced(): readonly ResidentView[] {
    return this.living.filter(({ name }) => !this.poses.has(name));
  }

  /** Towards whatever is beside a chore spot: the well, a bush, the notice board. */
  private facingTheWork({ x, y }: Point): Facing {
    return this.plan.grid.walkable(Math.floor(x) - 1, Math.floor(y)) ? "right" : "left";
  }
}

function standing(at: Point, facing: Facing = "right"): Pose {
  return { at, facing, atChore: false };
}

function facingTowards(from: Point, to: Point): Facing {
  return to.x < from.x ? "left" : "right";
}

/** `count` spots evenly spaced along half an ellipse behind the well, west to east, a tile in from the square's sides and top. */
function semicircleOf(plan: TownPlan, count: number): Point[] {
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

/** The walkable tiles of the town, each claimed by one Resident (or a lantern) at most. */
class Tiles {
  private readonly claimed = new Set<string>();

  constructor(private readonly grid: Grid) {}

  claim(at: Point): void {
    this.claimed.add(keyOf(at));
  }

  free(at: Point): boolean {
    const { x, y } = { x: Math.floor(at.x), y: Math.floor(at.y) };
    const onMap = x >= 0 && y >= 0 && x < this.grid.width && y < this.grid.height;
    return onMap && this.grid.walkable(x, y) && !this.claimed.has(keyOf(at));
  }

  /** Claim the first free spot of `spots`, starting `start` spots in and going round. */
  firstFree(spots: readonly Tile[], start: number): Point | null {
    for (let step = 0; step < spots.length; step += 1) {
      const spot = spots[(start + step) % spots.length];
      if (spot && this.free(spot)) return this.take(middleOf(spot));
    }
    return null;
  }

  /** Claim the free tile nearest to `to` (and also `fits`), the topmost then leftmost of equally near ones. */
  nearest(to: Point, fits: (tile: Tile) => boolean = () => true): Point | null {
    const candidates: Tile[] = [];
    for (let y = 0; y < this.grid.height; y += 1) {
      for (let x = 0; x < this.grid.width; x += 1) {
        if (this.free({ x, y }) && fits({ x, y })) candidates.push({ x, y });
      }
    }
    const away = (tile: Tile) => Math.hypot(middleOf(tile).x - to.x, middleOf(tile).y - to.y);
    const [best] = candidates.sort((a, b) => away(a) - away(b) || a.y - b.y || a.x - b.x);
    return best ? this.take(middleOf(best)) : null;
  }

  private take(at: Point): Point {
    this.claim(at);
    return at;
  }
}

function keyOf({ x, y }: Point): string {
  return `${Math.floor(x)},${Math.floor(y)}`;
}
