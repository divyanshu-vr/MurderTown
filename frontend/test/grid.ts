import type { Grid } from "../src/core/town/path";

/** A grid drawn as text: `#` cannot be walked, anything else can. */
export function gridOf(...rows: string[]): Grid {
  return {
    width: rows[0]?.length ?? 0,
    height: rows.length,
    walkable: (x, y) => rows[y]?.[x] !== "#",
  };
}
