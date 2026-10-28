/**
 * Finding a way across the town's tiles: the fewest steps, up, down, left or right, over tiles
 * that can be walked. Every step costs the same, so a breadth-first search finds a shortest
 * way; trying the four directions in a fixed order means the same two tiles always give the
 * same way, which keeps replays alike.
 */

export interface Tile {
  x: number;
  y: number;
}

export interface Grid {
  width: number;
  height: number;
  walkable(x: number, y: number): boolean;
}

const STEPS: readonly Tile[] = [
  { x: 0, y: -1 },
  { x: 1, y: 0 },
  { x: 0, y: 1 },
  { x: -1, y: 0 },
];

/** The tiles to step onto, in order, from `from` (not included) to `to`; null if there is no way. */
export function pathBetween(grid: Grid, from: Tile, to: Tile): Tile[] | null {
  const key = ({ x, y }: Tile) => y * grid.width + x;
  const cameFrom = new Map<number, Tile | null>([[key(from), null]]);
  const queue: Tile[] = [from];
  for (let next = queue.shift(); next; next = queue.shift()) {
    if (next.x === to.x && next.y === to.y) return walkedBack(cameFrom, next, key);
    for (const step of STEPS) {
      const tile = { x: next.x + step.x, y: next.y + step.y };
      if (!onMap(grid, tile) || !grid.walkable(tile.x, tile.y) || cameFrom.has(key(tile))) continue;
      cameFrom.set(key(tile), next);
      queue.push(tile);
    }
  }
  return null;
}

function onMap(grid: Grid, { x, y }: Tile): boolean {
  return x >= 0 && y >= 0 && x < grid.width && y < grid.height;
}

function walkedBack(cameFrom: Map<number, Tile | null>, end: Tile, key: (tile: Tile) => number): Tile[] {
  const way: Tile[] = [];
  for (let at: Tile | null | undefined = end; at && cameFrom.get(key(at)); at = cameFrom.get(key(at))) {
    way.unshift(at);
  }
  return way;
}
