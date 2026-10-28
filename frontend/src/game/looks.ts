/**
 * How the town looks: the Tiled map, the Kenney sheets it is drawn with (Tiny Town for the
 * town, Tiny Dungeon for its people, gravestones and ghosts), and which picture each seat wears. Tiny Dungeon has
 * thirteen townsfolk, so seats 13 and 14 wear the first two again in another colour.
 */
import peopleSheet from "../../assets/town/tiny-dungeon.png";
import townSheet from "../../assets/town/tiny-town.png";
import town from "../../assets/town/town.json";
import type { Point } from "../core/town/layout";

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
