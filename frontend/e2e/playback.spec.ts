/**
 * Playback in a real browser. A mocked socket streams the recorded game as a Spectator's
 * would (only what the whole town saw), the server's REST answers are mocked too, and the
 * page's clock is driven by the test, so time passes only when a test says.
 */
import { readFileSync } from "node:fs";

import { expect, type Page, test, type WebSocketRoute } from "@playwright/test";

import { isPublic } from "../src/core/gameView";
import type { GameSummary } from "../src/protocol";
import { recordedGame } from "../test/recordedGame";

const seen = recordedGame().filter(isPublic);

/** Where the built console looks for the server (its default `API_URL`). */
const API = "http://127.0.0.1:8000";

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

test("a Spectator holds, moves an event at a time and speeds up a game as it streams in, and is caught up when far behind", async ({
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
  await page.route(`${API}/**`, (route) => route.abort()); // the server is gone
  await page.route(({ pathname }) => pathname === "/a-game.ndjson", (route) =>
    route.fulfill({ body: readFileSync("../fixtures/scripted-game.ndjson", "utf-8") }),
  );
  await page.route(({ pathname }) => pathname === "/a-game.review.json", (route) =>
    route.fulfill({ body: readFileSync("../fixtures/scripted-game.review.json", "utf-8") }),
  );

  await page.goto("/replay?file=/a-game.ndjson");
  await expect(feedLines(page).first()).toBeVisible();
  await page.keyboard.press("l");

  await expect(page.getByRole("banner")).toContainText("Game over");
  await expect(page.getByRole("region", { name: "Post-game review" })).toContainText("Lies told");
  await page.getByRole("list", { name: "Residents" }).getByRole("button").first().click();
  await expect(page.getByRole("complementary", { name: /^Mind of / })).toBeVisible(); // folded from the file alone
});

test("the Host's replay shows the suspicion heatmap as it goes, and the review at the end", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("murdertown.host-token", "the-token"));
  await serveTheGame(page);
  await page.route(`${API}/games/abc/events`, (route) => route.fulfill({ json: { events: recordedGame() } }));
  await page.route(`${API}/games/abc/review`, (route) =>
    route.fulfill({ body: readFileSync("../fixtures/scripted-game.review.json", "utf-8") }),
  );
  await page.route(`${API}/games/abc/cost`, (route) => route.abort());

  await page.goto("/games/abc/replay");
  await page.keyboard.press("Space");
  await playback(page).getByRole("slider", { name: "Timeline" }).fill("300");
  await page.getByRole("tab", { name: "Suspicion" }).click();
  await expect(page.getByRole("table", { name: /^Suspicion at the start of Day/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Review" })).toHaveCount(0); // not before the end

  await page.keyboard.press("l");
  await page.getByRole("tab", { name: "Review" }).click();
  await expect(page.getByRole("region", { name: "Post-game review" })).toContainText("Influence");
});
