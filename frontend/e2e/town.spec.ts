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

/** The middle of a Resident's own door. */
const doorOf = (name: string) => middleOf(plan.doors[seats.get(name) ?? -1] ?? { x: -1, y: -1 });
const atTheirDoor = ({ name, x, y }: Standing) => x === doorOf(name).x && y === doorOf(name).y;
const playback = (page: Page) => page.getByRole("group", { name: "Playback" });

/** Hold playback and show the first `count` events. */
async function showTheFirst(page: Page, count: number): Promise<void> {
  await playback(page).getByRole("button", { name: "Hold" }).click();
  await page.getByRole("slider", { name: "Timeline" }).fill(String(count));
}

const firstMurder = eventsOf(events, "resident_died").find(({ payload }) => payload.cause === "murdered");

/** Moments to stand still at, by how many events have happened. */
const MOMENTS = {
  /** Day 3's Discussion (the second, since Day 1 is only a Night), a few words in, the dead where they fell. */
  "day-3-discussion": countWhen(events, "discussion", 2) + 6,
  /** Day 2's Dusk, the first, with every Conversation of its one wave under way. */
  "day-2-dusk": countOf(events, eventsOf(events, "conversation_message_posted")[0]),
  /** Day 1's Night, the game's opening, as the Murderers meet in the Den. */
  "day-1-night-den": countOf(events, eventsOf(events, "den_message_posted")[0]),
  /** Day 1's Night, as the Detective makes the last Visit, the Murderers and the Doctor home again. */
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
  expect(living.every(atTheirDoor)).toBe(false); // the Detective is out

  await page.keyboard.press("m");

  await expect.poll(async () => (await livingNow()).every(atTheirDoor)).toBe(true);
});

test("Night plays one Visit at a time: the Murderers strike and come home before the Doctor sets out", async ({ page }) => {
  const protection = eventsOf(events, "resident_protected").find(({ payload }) => payload.doctor !== payload.target);
  const victim = eventsOf(events, "victim_chosen").findLast(({ seq }) => seq < (protection?.seq ?? 0));
  if (!protection || !victim) throw new Error("the recorded game has a Night whose Doctor protects someone else");
  const near = (resident: Standing | undefined, door: { x: number; y: number }) =>
    resident !== undefined && Math.abs(resident.x - door.x) <= 1.5 && Math.abs(resident.y - door.y) <= 1.5;
  const { den, victim: target } = victim.payload;
  const { doctor, target: protectedOne } = protection.payload;

  await page.goto(await serveTheGameFile(page));
  await expect(page.locator("[data-resident]")).toHaveCount(12);
  await showTheFirst(page, countOf(events, victim) - 1);
  await playback(page).getByRole("combobox", { name: "Speed" }).selectOption("8");
  await playback(page).getByRole("button", { name: "Play" }).click();

  const samples: Standing[][] = [];
  const named = (sample: Standing[], name: string) => sample.find((resident) => resident.name === name);
  for (let tries = 0; tries < 300; tries++) {
    const sample = await standing(page);
    samples.push(sample);
    if (near(named(sample, doctor), doorOf(protectedOne))) break;
    await page.waitForTimeout(100);
  }

  expect(samples.some((sample) => den.every((murderer) => near(named(sample, murderer), doorOf(target))))).toBe(true);
  const doctorOut = samples.filter((sample) => !near(named(sample, doctor), doorOf(doctor)));
  expect(doctorOut.length).toBeGreaterThan(0);
  expect(doctorOut.every((sample) => den.every((murderer) => near(named(sample, murderer), doorOf(murderer))))).toBe(true);
});

test("mystery mode muffles every Conversation at Dusk", async ({ page }) => {
  const count = MOMENTS["day-2-dusk"];
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

// The camera, as a Spectator sees it: where the names over the Residents' heads land on screen.

/** The town standing still at Day 3's Discussion, everyone alive in the square; the two furthest apart, to watch. */
async function theSquare(page: Page): Promise<[string, string]> {
  const living = (await standStillAt(page, countWhen(events, "discussion", 2) + 1)).sort((a, b) => a.x - b.x);
  const [one, other] = [living[0], living.at(-1)];
  if (!one || !other || one.x === other.x) throw new Error("Expected Residents across the square");
  return [one.name, other.name];
}

/** Where a Resident's name is on screen: the middle of its bottom edge, just over their head. */
async function nameAt(page: Page, name: string): Promise<{ x: number; y: number }> {
  const box = await page.locator(`[data-resident="${name}"]`).boundingBox();
  if (!box) throw new Error(`${name}'s name is not drawn`);
  return { x: box.x + box.width / 2, y: box.y + box.height };
}

/** How far apart two names are on screen, which grows as the camera zooms in. */
async function apart(page: Page, one: string, other: string): Promise<number> {
  const [a, b] = [await nameAt(page, one), await nameAt(page, other)];
  return Math.hypot(a.x - b.x, a.y - b.y);
}

async function townViewBox(page: Page): Promise<{ x: number; y: number; width: number; height: number }> {
  const box = await page.getByRole("region", { name: "Town view" }).boundingBox();
  if (!box) throw new Error("The town is not drawn");
  return box;
}

async function middleOfTheTown(page: Page): Promise<{ x: number; y: number }> {
  const box = await townViewBox(page);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

/** The minimap's amber frame round the part of the town in view: how many of its pixels show in the Town view's bottom right corner, where the minimap sits, and how far across their middle is. */
async function theFrameInView(page: Page): Promise<{ pixels: number; across: number }> {
  const town = await townViewBox(page);
  const corner = { x: town.x + town.width - 200, y: town.y + town.height - 150, width: 200, height: 150 };
  const png = (await page.screenshot({ clip: corner })).toString("base64");
  return page.evaluate(async (data) => {
    const image = new Image();
    image.src = `data:image/png;base64,${data}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    [canvas.width, canvas.height] = [image.width, image.height];
    const context = canvas.getContext("2d");
    if (!context) throw new Error("No 2D canvas to read the screenshot with");
    context.drawImage(image, 0, 0);
    const rgba = context.getImageData(0, 0, image.width, image.height).data;
    let [pixels, across] = [0, 0];
    for (let i = 0; i < rgba.length; i += 4) {
      if (rgba[i] === 0xfc && rgba[i + 1] === 0xd3 && rgba[i + 2] === 0x4d) {
        pixels += 1;
        across += (i / 4) % image.width;
      }
    }
    return { pixels, across: pixels ? across / pixels : Number.NaN };
  }, png);
}

/** Hold a key down a moment, as a Spectator panning does. */
async function hold(page: Page, key: string): Promise<void> {
  await page.keyboard.down(key);
  await page.waitForTimeout(300);
  await page.keyboard.up(key);
}

/** Touch the screen with one finger or more, move them through `path`, and lift them. */
async function touch(page: Page, path: { x: number; y: number }[][]): Promise<void> {
  const [first, ...rest] = path;
  const screen = await page.context().newCDPSession(page);
  await screen.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: first ?? [] });
  for (const fingers of rest) await screen.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: fingers });
  await screen.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

test.describe("the camera", () => {
  test("a drag or W, A, S and D pan the view, and F frames the action again", async ({ page }) => {
    const [one] = await theSquare(page);
    const framed = await nameAt(page, one);
    const middle = await middleOfTheTown(page);

    await page.mouse.move(middle.x, middle.y);
    await page.mouse.down();
    await page.mouse.move(middle.x - 120, middle.y + 40, { steps: 6 });
    await page.mouse.up();
    await expect.poll(async () => (await nameAt(page, one)).x).toBeCloseTo(framed.x - 120, 0);
    await page.keyboard.press("f");
    await expect.poll(() => nameAt(page, one)).toEqual(framed);

    await hold(page, "d");
    expect((await nameAt(page, one)).x).toBeLessThan(framed.x - 20);
    await page.keyboard.press("f");
    await expect.poll(() => nameAt(page, one)).toEqual(framed);
  });

  test("the wheel, E and Q zoom in whole steps, and F frames the action again", async ({ page }) => {
    const [one, other] = await theSquare(page);
    const framed = await apart(page, one, other);
    const middle = await middleOfTheTown(page);

    await page.mouse.move(middle.x, middle.y);
    await page.mouse.wheel(0, -100);
    await expect.poll(() => apart(page, one, other)).toBeGreaterThan(framed * 1.2);
    const closer = await apart(page, one, other);
    await page.keyboard.press("q");
    await expect.poll(() => apart(page, one, other)).toBeCloseTo(framed, 0);
    await page.keyboard.press("e");
    await expect.poll(() => apart(page, one, other)).toBeCloseTo(closer, 0);

    await page.keyboard.press("f");
    await expect.poll(() => apart(page, one, other)).toBeCloseTo(framed, 0);

    await page.getByRole("combobox", { name: "Resident" }).focus(); // keys there choose, they do not zoom
    await page.keyboard.press("e");
    await page.waitForTimeout(300); // a few frames, in which a zoom would have shown
    expect(await apart(page, one, other)).toBeCloseTo(framed, 0);
  });

  test("a click on a Resident follows them, and F frames the action again", async ({ page }) => {
    const [one, other] = await theSquare(page);
    const framed = await nameAt(page, one);
    const spots = new Map((await standing(page)).map(({ name, x }) => [name, x]));
    const tilesApart = Math.abs((spots.get(one) ?? 0) - (spots.get(other) ?? 0));
    const perTile = Math.abs(framed.x - (await nameAt(page, other)).x) / tilesApart;
    const middle = await middleOfTheTown(page);

    await page.mouse.click(framed.x, framed.y + perTile / 2); // the middle of the Resident under the name

    // the view centres on them (as far as the town's edge lets it, which the square is far from)
    await expect.poll(async () => Math.abs((await nameAt(page, one)).x - middle.x)).toBeLessThan(perTile);
    await page.keyboard.press("f");
    await expect.poll(() => nameAt(page, one)).toEqual(framed);
  });

  test("the minimap frames the part of the town in view, wherever the view goes", async ({ page }) => {
    await theSquare(page);
    const framed = await theFrameInView(page);
    expect(framed.pixels).toBeGreaterThan(0);

    await hold(page, "a"); // the view goes left, and its frame on the minimap with it
    await expect.poll(async () => (await theFrameInView(page)).across).toBeLessThan(framed.across - 1);

    await page.keyboard.press("f");
    await expect.poll(() => theFrameInView(page)).toEqual(framed);
  });

  test.describe("on a touch screen", () => {
    test.use({ hasTouch: true });

    /** Two fingers, `from` apart, moving to `to` apart, about the middle of the town. */
    async function pinch(page: Page, from: number, to: number): Promise<void> {
      const { x, y } = await middleOfTheTown(page);
      const steps = [0, 0.25, 0.5, 0.75, 1].map((done) => (from + (to - from) * done) / 2);
      await touch(
        page,
        steps.map((half) => [
          { x: x - half, y },
          { x: x + half, y },
        ]),
      );
    }

    test("a pinch zooms a step at a time, as far as a notch of the wheel, out as well as in", async ({ page }) => {
      const [one, other] = await theSquare(page);
      const framed = await apart(page, one, other);
      const { x, y } = await middleOfTheTown(page);
      await page.mouse.move(x, y);
      await page.mouse.wheel(0, -100);
      await expect.poll(() => apart(page, one, other)).toBeGreaterThan(framed * 1.1);
      const aNotch = await apart(page, one, other);
      await page.keyboard.press("f");
      await expect.poll(() => apart(page, one, other)).toBeCloseTo(framed, 0);

      await pinch(page, 80, 104); // spread by 1.3: one step
      await expect.poll(() => apart(page, one, other)).toBeCloseTo(aNotch, 0);

      await pinch(page, 104, 80); // and back
      await expect.poll(() => apart(page, one, other)).toBeCloseTo(framed, 0);
    });

    test("a one-finger drag pans", async ({ page }) => {
      const [one] = await theSquare(page);
      const framed = await nameAt(page, one);
      const { x, y } = await middleOfTheTown(page);

      await touch(
        page,
        [0, 30, 60, 90, 120].map((moved) => [{ x: x - moved, y }]),
      );

      await expect.poll(async () => (await nameAt(page, one)).x).toBeCloseTo(framed.x - 120, 0);
    });
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
