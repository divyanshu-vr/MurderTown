/**
 * The replay site (`pnpm build:site`), served as a static host would serve it. It lists its
 * recorded games and plays them in the town, in full scope or in Mystery mode, from its own files
 * alone: in every test here, no request ever leaves the site.
 */
import { expect, test } from "@playwright/test";

import index from "../public/site/index.json" with { type: "json" };

let asked: URL[] = [];

test.beforeEach(({ page }) => {
  asked = [];
  page.on("request", (request) => asked.push(new URL(request.url())));
});

test.afterEach(({ baseURL }) => {
  const site = new URL(baseURL ?? "").origin;
  expect(asked.filter((url) => url.origin !== site).map(String)).toEqual([]);
});

test("the landing page lists every recorded game", async ({ page }) => {
  await page.goto("/");

  const games = page.getByRole("list", { name: "Recorded games" }).getByRole("listitem");
  await expect(games).toHaveCount(index.length);
  for (const game of index) await expect(page.getByRole("heading", { name: game.title })).toBeVisible();
});

test("a recorded game plays in the town to its end from the site's own files", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Watch", exact: true }).first().click();

  await expect(page.getByRole("log", { name: "Town feed" }).getByRole("listitem").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Town view" })).toBeVisible();
  await page.keyboard.press("l");
  await expect(page.getByRole("banner")).toContainText("Game over");
});

test("a recorded game watched in Mystery mode starts in it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Watch in Mystery mode" }).first().click();

  await expect(page.getByRole("button", { name: "Mystery mode" })).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("l");
  await expect(page.getByRole("banner")).toContainText("Game over");
});

test("a link to a game from anywhere else shows the site's own games instead", async ({ page }) => {
  await page.goto(`/replay?file=${encodeURIComponent("http://127.0.0.1:8000/forged.ndjson")}`);

  await expect(page.getByRole("list", { name: "Recorded games" })).toBeVisible();
});

test("any other address shows the recorded games: there is nothing else to see", async ({ page }) => {
  await page.goto("/setup");

  await expect(page.getByRole("list", { name: "Recorded games" })).toBeVisible();
});
