/**
 * How the town looks: the Tiled map, the Kenney sheets it is drawn with (Tiny Town for the
 * town and the tools of each Chore, Tiny Dungeon for its people, gravestones and ghosts), and which picture each seat wears. Tiny Dungeon has
 * thirteen townsfolk, so seats 13 and 14 wear the first two again in another colour.
 */
import peopleSheet from "../../assets/town/tiny-dungeon.png";
import townSheet from "../../assets/town/tiny-town.png";
import town from "../../assets/town/town.json";
import type { Point } from "../core/town/layout";
import type { ChoreKind } from "../core/town/plan";

export const TOWN_MAP = town;

/** A tile's size, in pixels. */
export const TILE = town.tilewidth;

/** Where a spot in town (in tiles) is drawn, in the world's pixels. */
export function toPixels({ x, y }: Point): Point {
  return { x: x * TILE, y: y * TILE };
}

export const SHEETS = {
  /** The tileset's name in the map is its key. */
  town: { key: "tiny-town", url: townSheet },
  people: { key: "tiny-dungeon", url: peopleSheet },
} as const;

/** The townsfolk in Tiny Dungeon, by frame; they look slightly to the left. */
const TOWNSFOLK = [84, 85, 86, 87, 88, 96, 97, 98, 99, 100, 109, 111, 112] as const;
const SECOND_LOOK = 0xa8c0ff;

export const GRAVESTONE = 65;
export const GHOST = 121;

/** How a tool moves as the work goes on: lowered and raised, tipped, or swung. */
export type ToolMotion = "dip" | "tip" | "swing";

/** The tool each Chore is done with, from the town's sheet, and how it moves. */
export const CHORE_TOOLS: Record<ChoreKind, { frame: number; motion: ToolMotion }> = {
  "draw water": { frame: 130, motion: "dip" }, // an empty bucket, let down into the well and drawn up again
  "water the garden": { frame: 131, motion: "tip" }, // a bucket of water, tipped over the plants
  "chop wood": { frame: 127, motion: "swing" }, // an axe, swung at the trees
};

export interface Look {
  frame: number;
  tint: number | null;
}

export function lookOf(seat: number): Look {
  return {
    frame: TOWNSFOLK[seat % TOWNSFOLK.length] ?? TOWNSFOLK[0],
    tint: seat >= TOWNSFOLK.length ? SECOND_LOOK : null,
  };
}
