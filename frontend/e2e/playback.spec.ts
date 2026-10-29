/**
 * Playback in a real browser. A mocked socket streams the recorded game as a Spectator's
 * would (only what the whole town saw), the server's REST answers are mocked too, and the
 * page's clock is driven by the test, so time passes only when a test says.
 *
 * These watch the console alone, as a browser without WebGL does; town.spec.ts watches the town.
 */
import { expect, type Page, test, type WebSocketRoute } from "@playwright/test";

import { isPublic } from "../src/core/gameView";
import type { GameSummary } from "../src/protocol";
import { NIGHT_LINES } from "../test/feedLines";
import { recordedGame, recordedReview } from "../test/recordedGame";
import { API, serveTheGameFile, withoutWebGL } from "./gameFile";

const seen = recordedGame().filter(isPublic);

test.beforeEach(({ page }) => withoutWebGL(page));

/** The server, as a Spectator's browser reaches it: the game's summary and its whole log. */
async function serveTheGame(page: Page): Promise<void> {
  const summary: GameSummary = {
    id: "abc",
    status: "running",
    winner: null,
    created_at: "2026-10-28T10:00:00Z",
    last_seq: 0,
    day: 1,
    phase: "dawn",
    cost_usd: null,
    controls: [],
  };
  await page.route(`${API}/games/abc`, (route) => route.fulfill({ json: summary }));
  await page.route(`${API}/games/abc/events`, (route) => route.fulfill({ json: { events: seen } }));
}

function feedLines(page: Page) {
  return page.getByRole("log", { name: "Town feed" }).getByRole("listitem");
}

function playback(page: Page) {
  return page.getByRole("group", { name: "Playback" });
}

test("a Spectator holds, moves an event at a time and speeds up a game as it streams in, and catches up when far behind", async ({
  page,
}) => {
  await page.clock.install();
  await serveTheGame(page);
  let socket: WebSocketRoute | undefined;
  await page.routeWebSocket(/\/ws\/games\/abc/, (connected) => {
    socket = connected;
  });
  await page.goto("/games/abc");
  await expect.poll(() => socket).toBeDefined();
  const stream = (events: typeof seen) => events.forEach((event) => socket?.send(JSON.stringify(event)));

  stream(seen.slice(0, 6));
  await page.clock.runFor(100);
  await expect(feedLines(page)).toHaveCount(1);
  await expect(playback(page)).toContainText("5 events behind");

  await playback(page).getByRole("button", { name: "Hold" }).click();
  await page.clock.runFor(10_000); // five events' worth of time
  await expect(feedLines(page)).toHaveCount(1);

  await playback(page).getByRole("button", { name: "Next event" }).click();
  await expect(feedLines(page)).toHaveCount(2);

  await playback(page).getByRole("combobox", { name: "Speed" }).selectOption("8");
  await playback(page).getByRole("button", { name: "Play" }).click();
  await page.clock.runFor(10_000);
  await expect(feedLines(page)).toHaveCount(6);
  await expect(playback(page).getByRole("button", { name: "Skip to live" })).toBeDisabled();

  stream(seen.slice(6)); // the rest of the game at once: far more than a minute behind
  await page.clock.runFor(100);
  // the page reads a thousand events as they arrive, which a busy CI runner takes a while to do
  await expect(playback(page)).toContainText("catching up at 24.0×", { timeout: 30_000 }); // three times 8×
  await expect(feedLines(page)).not.toHaveCount(6);

  await playback(page).getByRole("button", { name: "Skip to live" }).click();
  await expect(page.getByRole("banner")).toContainText("Game over");
});

test("a finished game replays from its start, steered from the keyboard, with a link to share it", async ({
  page,
}) => {
  await page.clock.install();
  await serveTheGame(page);
  await page.goto("/games/abc/replay");
  await page.clock.runFor(100);
  await expect(feedLines(page)).toHaveCount(1);

  await page.keyboard.press("Space");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(feedLines(page)).toHaveCount(3);
  await expect(playback(page).getByRole("button", { name: "Play" })).toBeVisible();

  await page.keyboard.press("l");
  await expect(page.getByRole("banner")).toContainText("Game over");
  await expect(playback(page).getByRole("link", { name: "Replay link" })).toHaveAttribute(
    "href",
    "http://localhost:4173/games/abc/replay",
  );
});

test("new lines fade in, unless the Spectator prefers reduced motion", async ({ page }) => {
  await serveTheGame(page);
  const animationOfFirstLine = () =>
    feedLines(page)
      .first()
      .evaluate((line) => getComputedStyle(line).animationName);

  await page.goto("/games/abc/replay");
  await expect.poll(animationOfFirstLine).toBe("appear");

  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(animationOfFirstLine).toBe("none");
});

test("a game file replays with no server at all, ending with the review beside it", async ({ page }) => {
  await page.goto(await serveTheGameFile(page));
  await expect(feedLines(page).first()).toBeVisible();
  await page.keyboard.press("l");

  await expect(page.getByRole("banner")).toContainText("Game over");
  await expect(page.getByRole("region", { name: "Post-game review" })).toContainText("Lies told");
  await page.getByRole("list", { name: "Residents" }).getByRole("button").first().click();
  await expect(page.getByRole("complementary", { name: /^Mind of / })).toBeVisible(); // folded from the file alone
});

/** The lines whose drawing the browser is skipping, as it reports them. */
interface Skipping {
  skipped: Set<Element>;
}

test("a long game's feed filters by Resident and by kind, and shows everything again", async ({ page }) => {
  await page.addInitScript(() => {
    const skipping = window as unknown as Skipping;
    skipping.skipped = new Set();
    const note = (event: Event) => {
      const line = event.target as Element;
      if ((event as Event & { skipped: boolean }).skipped) skipping.skipped.add(line);
      else skipping.skipped.delete(line);
    };
    document.addEventListener("contentvisibilityautostatechange", note, true);
  });
  const resident = recordedGame().find((event) => event.payload.type === "role_assigned");
  if (resident?.payload.type !== "role_assigned") throw new Error("The recorded game has no roles");
  const name = resident.payload.resident;
  await page.goto(await serveTheGameFile(page));
  await expect(feedLines(page).first()).toBeVisible();
  await page.keyboard.press("l");
  await expect(page.getByRole("banner")).toContainText("Game over");
  await page.getByRole("tab", { name: "Feed" }).click(); // the review opens by itself at the end
  const everything = await feedLines(page).count();

  // following the end, the newest line is wholly in view, and the browser skips drawing lines far above
  const log = await page.getByRole("log", { name: "Town feed" }).boundingBox();
  const bottomOf = async () => {
    const line = await feedLines(page).last().boundingBox();
    return line ? line.y + line.height : Infinity;
  };
  await expect.poll(bottomOf).toBeLessThanOrEqual((log?.y ?? 0) + (log?.height ?? 0));
  const skipped = (line: Element) => (window as unknown as Skipping).skipped.has(line);
  await expect.poll(() => feedLines(page).first().evaluate(skipped)).toBe(true);
  expect(await feedLines(page).last().evaluate(skipped)).toBe(false);

  await page.getByRole("combobox", { name: "Resident" }).selectOption(name);
  // every line names them, but the headings and the reveal, which tells everyone's role
  const followed = await feedLines(page).evaluateAll((lines) =>
    lines
      .filter((line) => line.dataset.kind !== "phase_started" && line.dataset.kind !== "roles_revealed")
      .map((line) => line.textContent ?? ""),
  );
  expect(followed.length).toBeGreaterThan(0);
  expect(followed.every((line) => line.includes(name))).toBe(true);

  await page.getByRole("button", { name: "Show everything" }).click();
  const show = page.getByRole("group", { name: "Show" });
  for (const kind of ["Public", "Private", "System"]) await show.getByRole("button", { name: kind }).click();
  const kinds = await feedLines(page).evaluateAll((lines) =>
    lines.map((line) => line.dataset.kind).filter((kind) => kind !== "phase_started"),
  );
  expect(new Set(kinds)).toEqual(new Set(NIGHT_LINES));

  await page.getByRole("button", { name: "Show everything" }).click();
  await expect(feedLines(page)).toHaveCount(everything);
});

test("the Host's replay shows the suspicion heatmap as it goes, and the review at the end", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("murdertown.host-token", "the-token"));
  await serveTheGame(page);
  await page.route(`${API}/games/abc/events`, (route) => route.fulfill({ json: { events: recordedGame() } }));
  await page.route(`${API}/games/abc/review`, (route) => route.fulfill({ json: recordedReview() }));
  await page.route(`${API}/games/abc/cost`, (route) => route.abort());

  await page.goto("/games/abc/replay");
  await playback(page).getByRole("button", { name: "Hold" }).click(); // once the replay is ready, unlike a key press
  await playback(page).getByRole("slider", { name: "Timeline" }).fill("300");
  await page.getByRole("tab", { name: "Suspicion" }).click();
  await expect(page.getByRole("table", { name: /^Suspicion at the start of Day/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Review" })).toHaveCount(0); // not before the end

  await page.keyboard.press("l");
  await page.getByRole("tab", { name: "Review" }).click();
  await expect(page.getByRole("region", { name: "Post-game review" })).toContainText("Influence");
});
