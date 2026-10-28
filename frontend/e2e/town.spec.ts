/**
 * The town in a real browser, replaying the recorded game from a file. Where everyone stands is
 * read from the names over their heads, which carry their spot in tiles, and checked against the
 * places on the map file itself. `?deterministic=1` makes the town stand still for its screenshot, which is
 * compared on Linux only, where its baseline is made (`pnpm e2e:linux`, as CI runs it).
 */
import { expect, type Page, test } from "@playwright/test";

import town from "../assets/town/town.json" with { type: "json" };
import { foldEvents, isPublic } from "../src/core/gameView";
import { middleOf } from "../src/core/town/layout";
import { inArea, planOf } from "../src/core/town/plan";
import { stageOf } from "../src/core/town/stage";
import { countOf, countWhen, eventsOf, payloadsOf, recordedGame } from "../test/recordedGame";
import { serveTheGameFile, withoutWebGL } from "./gameFile";

const events = recordedGame();
const seats = new Map(payloadsOf(events, "game_started")[0]?.residents.map(({ name, seat }) => [name, seat]));
const plan = planOf(town);

interface Standing {
  name: string;
  x: number;
  y: number;
  dead: boolean;
}

function standing(page: Page): Promise<Standing[]> {
  return page.locator("[data-resident]").evaluateAll((names) =>
    names.map((name) => {
      const { resident = "", x = "NaN", y = "NaN", dead } = (name as HTMLElement).dataset;
      return { name: resident, x: Number(x), y: Number(y), dead: dead === "true" };
    }),
  );
}

const inTheSquare = (resident: Standing) => inArea(plan.square, resident);

const atTheirDoor = ({ name, x, y }: Standing) => {
  const door = plan.doors[seats.get(name) ?? -1];
  return door !== undefined && x === middleOf(door).x && y === middleOf(door).y;
};

/** Hold playback and show the first `count` events. */
async function showTheFirst(page: Page, count: number): Promise<void> {
  await page.getByRole("group", { name: "Playback" }).getByRole("button", { name: "Hold" }).click();
  await page.getByRole("slider", { name: "Timeline" }).fill(String(count));
}

const firstMurder = eventsOf(events, "resident_died").find(({ payload }) => payload.cause === "murdered");

/** Moments to stand still at, by how many events have happened. */
const MOMENTS = {
  /** Day 3's Discussion, a few words in: one Resident banished in the square, one murdered at home. */
  "day-3-discussion": countWhen(events, "discussion", 3) + 6,
  /** Day 1's Dusk, at the end of its first wave of Conversations. */
  "day-1-dusk": countOf(events, eventsOf(events, "conversation_started")[3]) - 1,
  /** Day 1's Night, as the Murderers meet in the Den. */
  "day-1-night-den": countOf(events, eventsOf(events, "den_message_posted")[0]),
  /** Day 1's Night, once the Murderers, the Doctor and the Detective have all made their visits. */
  "day-1-night": countOf(events, eventsOf(events, "resident_investigated")[0]),
  /** The Dawn of the first murder, with the Victim's ghost over their grave and the Narrator's Recap. */
  "first-murder-dawn": countOf(events, eventsOf(events, "recap_narrated").find(({ seq }) => seq > (firstMurder?.seq ?? Infinity))),
};

/** Open the town standing still once `count` events have happened and everyone in it is placed; the living, where they stand. */
async function standStillAt(page: Page, count: number): Promise<Standing[]> {
  await page.goto(`${await serveTheGameFile(page)}&deterministic=1`);
  await expect(page.locator("[data-resident]")).toHaveCount(12);
  await showTheFirst(page, count);
  const living = foldEvents(events.slice(0, count)).residents.filter(({ fate }) => fate === null);
  const standingLiving = async () => (await standing(page)).filter((resident) => !resident.dead);
  await expect.poll(async () => (await standingLiving()).map(({ name }) => name).sort()).toEqual(living.map(({ name }) => name).sort());
  return standingLiving();
}

test("every living Resident stands in the square during Discussion", async ({ page }) => {
  const living = await standStillAt(page, MOMENTS["day-3-discussion"]);

  expect(living.every(inTheSquare)).toBe(true);
});

for (const [moment, count] of Object.entries(MOMENTS)) {
  test(`the town standing still at ${moment} looks the same every time`, async ({ page }) => {
    test.skip(process.platform !== "linux", "the baselines are made on Linux: run pnpm e2e:linux");
    await standStillAt(page, count);

    await expect(page.getByRole("region", { name: "Town view" })).toHaveScreenshot(`${moment}.png`);
  });
}

test("mystery mode keeps the Den and the visits out of the town", async ({ page }) => {
  const living = await standStillAt(page, MOMENTS["day-1-night"]);
  const livingNow = async () => (await standing(page)).filter((resident) => !resident.dead);
  expect(living.every(atTheirDoor)).toBe(false); // the Murderers, the Doctor and the Detective are out

  await page.keyboard.press("m");

  await expect.poll(async () => (await livingNow()).every(atTheirDoor)).toBe(true);
});

test("mystery mode muffles every Conversation at Dusk", async ({ page }) => {
  const count = MOMENTS["day-1-dusk"];
  const heard = stageOf(events.slice(0, count).filter(isPublic));
  await standStillAt(page, count);
  const town = page.getByRole("region", { name: "Town view" });
  await expect(town.getByText("I don't trust").first()).toBeVisible();

  await page.keyboard.press("m");

  await expect(town.getByText("· · ·", { exact: true })).toHaveCount(heard.pairs.length);
  await expect(town.getByText("I don't trust")).toHaveCount(0);
});

test("seeking snaps everyone to where they belong at once, rather than walking there", async ({ page }) => {
  await page.goto(await serveTheGameFile(page));
  await expect(page.locator("[data-resident]")).toHaveCount(12);
  const living = async () => (await standing(page)).filter((resident) => !resident.dead);

  await page.getByRole("slider", { name: "Timeline" }).fill(String(countWhen(events, "dawn", 2)));
  await expect.poll(async () => (await living()).every(atTheirDoor), { timeout: 1000 }).toBe(true);

  await page.getByRole("slider", { name: "Timeline" }).fill(String(countWhen(events, "discussion", 2) + 1));
  await expect.poll(async () => (await living()).every(inTheSquare), { timeout: 1000 }).toBe(true);
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the town keeps the map's shape above the panels, which become tabs", async ({ page }) => {
    await page.goto(await serveTheGameFile(page));
    const townBox = await page.getByRole("region", { name: "Town view" }).boundingBox();
    const feedBox = await page.getByRole("log", { name: "Town feed" }).boundingBox();

    expect(townBox?.width).toBe(390);
    expect(townBox?.height).toBeCloseTo((390 * town.height) / town.width, 0);
    expect(feedBox?.y).toBeGreaterThanOrEqual((townBox?.y ?? 0) + (townBox?.height ?? 0));
    await page.getByRole("tab", { name: "Residents" }).click();
    await expect(page.getByRole("list", { name: "Residents" })).toBeVisible();
  });
});

test("without WebGL, the console plays on alone and never downloads the town", async ({ page }) => {
  await withoutWebGL(page);
  const asked: string[] = [];
  page.on("request", (request) => asked.push(request.url()));

  await page.goto(await serveTheGameFile(page));
  await expect(page.getByRole("log", { name: "Town feed" }).getByRole("listitem").first()).toBeVisible();
  await page.keyboard.press("l");

  await expect(page.getByRole("banner")).toContainText("Game over");
  await expect(page.getByRole("region", { name: "Town view" })).toHaveCount(0);
  expect(asked.filter((url) => /TownCanvas|phaser/i.test(url))).toEqual([]);
});
