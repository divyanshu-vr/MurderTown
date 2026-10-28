/**
 * Makes the README's pictures from a game on the replay site: a GIF of the town through the
 * game's first Day, and one Resident's Mind inspector as Day 2's Discussion begins. Serve the
 * site first (`pnpm build:site && pnpm exec vite preview --mode site --port 4174`); the GIF needs
 * ffmpeg. Usage: `pnpm capture:readme <game file under public/site> <Resident>`.
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium, type Page } from "@playwright/test";

import type { Event } from "../src/protocol";

function argument(index: number): string {
  const value = process.argv[2 + index];
  if (!value) throw new Error("Usage: pnpm capture:readme <game file under public/site> <Resident>");
  return value;
}

const game = argument(0);
const resident = argument(1);
const site = process.env.SITE ?? "http://localhost:4174";
const frontend = join(import.meta.dirname, "..");
const images = join(frontend, "..", "docs", "images");
const watch = `${site}/replay?file=${encodeURIComponent(`/site/${game}`)}`;
const viewport = { width: 1280, height: 720 };

/** How many of the game's events have happened once Day 2's Discussion has begun. */
function untilDayTwo(): number {
  const lines = readFileSync(join(frontend, "public", "site", game), "utf-8").trim().split("\n");
  const events = lines.map((line) => JSON.parse(line) as Event);
  const start = events.findIndex(
    ({ payload }) => payload.type === "phase_started" && payload.day === 2 && payload.phase === "discussion",
  );
  if (start < 0) throw new Error(`${game} has no Day 2 to show a mind at`);
  return start + 1;
}

async function townThroughDayOne(page: Page): Promise<{ x: number; y: number; width: number; height: number }> {
  await page.goto(watch);
  await page.getByRole("combobox", { name: "Speed" }).selectOption("8");
  await page.getByRole("banner").getByText("Day 2", { exact: false }).waitFor({ timeout: 600_000 });
  const town = await page.getByRole("region", { name: "Town view" }).boundingBox();
  if (!town) throw new Error("The town was not drawn");
  return town;
}

async function mindInspector(page: Page): Promise<void> {
  await page.goto(watch);
  await page.getByRole("group", { name: "Playback" }).getByRole("button", { name: "Hold" }).click();
  await page.getByRole("slider", { name: "Timeline" }).fill(String(untilDayTwo()));
  await page.getByRole("tab", { name: "Residents" }).click();
  await page.getByRole("button", { name: resident, exact: true }).click();
  await page.waitForTimeout(1500); // let the town settle behind the panel
  await page.screenshot({ path: join(images, "mind-inspector.png") });
}

const browser = await chromium.launch();
const videos = mkdtempSync(join(tmpdir(), "murdertown-capture-"));
const recording = await browser.newContext({ viewport, recordVideo: { dir: videos, size: viewport } });
const town = await townThroughDayOne(await recording.newPage());
await recording.close(); // the video is written as the page closes
const still = await browser.newContext({ viewport: { width: 1280, height: 860 } });
await mindInspector(await still.newPage());
await browser.close();

// The town and the bars above it, from the moment it is drawn: 5 frames a second, 640 pixels wide,
// and one palette without dithering, which keeps pixel art crisp and the file a few megabytes.
const video = join(videos, readdirSync(videos)[0] ?? "");
const crop = `crop=${Math.round(town.x + town.width)}:${viewport.height}:0:0`;
const palette = "split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none";
const gif = spawnSync(
  "ffmpeg",
  [
    ...["-y", "-loglevel", "error", "-ss", "3", "-i", video],
    ...["-vf", `${crop},fps=5,scale=640:-1:flags=neighbor,${palette}:diff_mode=rectangle`],
    join(images, "town-day.gif"),
  ],
  { stdio: "inherit" },
);
process.exit(gif.status ?? 1);
