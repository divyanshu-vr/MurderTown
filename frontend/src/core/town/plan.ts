/**
 * The town as its map lays it out: which tiles can be walked, and where the square, the well,
 * the town hall and each seat's door are. Read from the Tiled map the town is drawn from, so
 * moving a house in Tiled moves where its Resident lives.
 *
 * The map has a `props` layer whose blocking tiles carry the tileset property `collides`, and a
 * `places` object layer: a `square` rectangle; `well`, `hall`, `den` (in front of its door) and
 * `den window` points; a `door` point per seat (the tile in front of the door, with a `seat`
 * property); and as many `lantern`, `chore` and `wander` points as the town has.
 */
import type { Grid, Tile } from "./path";

/** The parts of a Tiled map (JSON format) the plan reads. */
export interface TiledMap {
  width: number;
  height: number;
  tilewidth: number;
  layers: readonly TiledLayer[];
  tilesets: readonly TiledTileset[];
}

interface TiledLayer {
  name: string;
  data?: readonly number[] | undefined;
  objects?: readonly TiledObject[] | undefined;
}

interface TiledObject {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  properties?: readonly TiledProperty[] | undefined;
}

interface TiledTileset {
  firstgid: number;
  tiles?: readonly { id: number; properties?: readonly TiledProperty[] | undefined }[] | undefined;
}

interface TiledProperty {
  name: string;
  value: unknown;
}

/** A rectangle of tiles. */
export interface Area {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TownPlan {
  grid: Grid;
  square: Area;
  well: Tile;
  hall: Tile;
  /** The tile in front of each seat's door, by seat. */
  doors: readonly Tile[];
  /** In front of the Den's door, and its window, which lights up while the Murderers meet. */
  den: Tile;
  denWindow: Tile;
  lanterns: readonly Tile[];
  /** Where a Resident can do a Chore at Dusk, and where those wandering stop. */
  chores: readonly Tile[];
  wanders: readonly Tile[];
}

export function planOf(map: TiledMap): TownPlan {
  const size = map.tilewidth;
  const places = layerNamed(map, "places").objects ?? [];
  const placed = (name: string) => places.filter((place) => place.name === name);
  const tileOf = (place: TiledObject): Tile => ({ x: Math.floor(place.x / size), y: Math.floor(place.y / size) });
  const only = (name: string) => {
    const [place] = placed(name);
    if (!place) throw new Error(`The town's map has no ${name}`);
    return place;
  };
  const square = only("square");
  const doors = placed("door")
    .map((door) => ({ seat: Number(propertyOf(door.properties, "seat")), tile: tileOf(door) }))
    .sort((a, b) => a.seat - b.seat)
    .map((door) => door.tile);
  return {
    grid: gridOf(map),
    square: { ...tileOf(square), width: square.width / size, height: square.height / size },
    well: tileOf(only("well")),
    hall: tileOf(only("hall")),
    doors,
    den: tileOf(only("den")),
    denWindow: tileOf(only("den window")),
    lanterns: placed("lantern").map(tileOf),
    chores: placed("chore").map(tileOf),
    wanders: placed("wander").map(tileOf),
  };
}

export function inArea(area: Area, { x, y }: Tile): boolean {
  return x >= area.x && y >= area.y && x < area.x + area.width && y < area.y + area.height;
}

/** Every tile can be walked unless something on the `props` layer collides. */
function gridOf(map: TiledMap): Grid {
  const blocking = new Set(
    map.tilesets.flatMap((tileset) =>
      (tileset.tiles ?? [])
        .filter((tile) => propertyOf(tile.properties, "collides") === true)
        .map((tile) => tileset.firstgid + tile.id),
    ),
  );
  const props = layerNamed(map, "props").data ?? [];
  return {
    width: map.width,
    height: map.height,
    walkable: (x, y) => !blocking.has(props[y * map.width + x] ?? 0),
  };
}

function layerNamed(map: TiledMap, name: string): TiledLayer {
  const layer = map.layers.find((each) => each.name === name);
  if (!layer) throw new Error(`The town's map has no ${name} layer`);
  return layer;
}

function propertyOf(properties: readonly TiledProperty[] | undefined, name: string): unknown {
  return properties?.find((property) => property.name === name)?.value;
}
