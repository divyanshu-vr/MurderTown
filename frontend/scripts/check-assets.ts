/**
 * Checks the town's art before it ships: every sheet is a whole number of 16 by 16 frames and is
 * credited in ATTRIBUTION.md, and the Tiled map embeds its tilesets, at 16 pixels a tile, sized
 * to the sheets they name, using only tiles they hold. Run with `pnpm check:assets`.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import type { TiledMap } from "../src/core/town/plan";

const FOLDER = join(import.meta.dirname, "..", "assets", "town");
const FRAME = 16;

/** A tileset as Tiled writes it, with all a check needs. */
interface Tileset {
  name: string;
  source?: string;
  image?: string;
  imagewidth?: number;
  imageheight?: number;
  tilewidth?: number;
  tileheight?: number;
  columns?: number;
  tilecount?: number;
  firstgid: number;
  margin?: number;
  spacing?: number;
}

type CheckedMap = Omit<TiledMap, "tilesets"> & { tileheight: number; tilesets: Tileset[] };

const problems: string[] = [];

/** A PNG's size, read from its header. */
function sizeOf(file: string): { width: number; height: number } {
  const header = readFileSync(join(FOLDER, file)).subarray(0, 24);
  if (header.toString("latin1", 12, 16) !== "IHDR") throw new Error(`${file} is not a PNG`);
  return { width: header.readUInt32BE(16), height: header.readUInt32BE(20) };
}

const sheets = readdirSync(FOLDER).filter((file) => file.endsWith(".png"));
const credits = readFileSync(join(FOLDER, "ATTRIBUTION.md"), "utf-8");
for (const sheet of sheets) {
  const { width, height } = sizeOf(sheet);
  if (width % FRAME || height % FRAME) problems.push(`${sheet} is ${width}x${height}, not whole ${FRAME}x${FRAME} frames`);
  if (!credits.includes(sheet)) problems.push(`ATTRIBUTION.md does not credit ${sheet}`);
}

const map = JSON.parse(readFileSync(join(FOLDER, "town.json"), "utf-8")) as CheckedMap;
if (map.tilewidth !== FRAME || map.tileheight !== FRAME) problems.push(`the map's tiles are not ${FRAME} pixels`);
for (const tileset of map.tilesets) {
  const name = `the map's tileset ${tileset.name}`;
  if (tileset.source) {
    problems.push(`${name} is not embedded (Phaser cannot load ${tileset.source})`);
    continue;
  }
  if (!tileset.image || !existsSync(join(FOLDER, tileset.image))) {
    problems.push(`${name} names no sheet beside the map`);
    continue;
  }
  const { width, height } = sizeOf(tileset.image);
  if (tileset.tilewidth !== FRAME || tileset.tileheight !== FRAME) problems.push(`${name} is not ${FRAME} pixels a tile`);
  if (tileset.imagewidth !== width || tileset.imageheight !== height) problems.push(`${name} expects another size of ${tileset.image}`);
  if (tileset.margin || tileset.spacing) problems.push(`${name} has a margin or spacing the packed sheets do not`);
  if (tileset.columns !== width / FRAME || tileset.tilecount !== (width / FRAME) * (height / FRAME)) {
    problems.push(`${name} counts other tiles than ${tileset.image} holds`);
  }
}

const ranges = map.tilesets.map(({ firstgid, tilecount = 0 }) => ({ from: firstgid, to: firstgid + tilecount - 1 }));
for (const layer of map.layers) {
  const unknown = (layer.data ?? []).filter((gid) => gid !== 0 && !ranges.some(({ from, to }) => gid >= from && gid <= to));
  if (unknown.length) problems.push(`the map's ${layer.name} layer uses tiles no tileset holds: ${[...new Set(unknown)].join(", ")}`);
}

if (problems.length) {
  console.error(`The town's assets need fixing:\n${problems.map((problem) => `- ${problem}`).join("\n")}`);
  process.exit(1);
}
console.log(`The town's assets are in order: ${sheets.length} sheets and the map.`);
