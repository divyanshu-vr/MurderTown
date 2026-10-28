/**
 * The replay site's games: every game its list names is beside it, whole, with its review, and
 * holds nothing from outside the game. The repository and the site are public, so a recorded
 * game must never carry an email address, a path on the Host's computer or anything shaped like
 * a credential. These patterns are deliberately wider than the backend's scrubber, so the check
 * does not miss what the scrubber missed. And the site plays only its own games.
 */
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { eventsInGameFile } from "../core/gameFile";
import index from "../../public/site/index.json" with { type: "json" };
import { addressOf, isSiteGame, type SiteGame } from "./replaySite";
import { reviewBeside } from "./review";

const PUBLIC = resolve(process.cwd(), "public");

const OUTSIDE_WORLD = [
  /[\w.+-]+@[\w-]+(\.[\w-]+)+/, // an email address
  /\b[A-Za-z]:[\\/]/, // a Windows drive, either slash
  /(^|[\s"'(])\/(home|Users|root|tmp|var|mnt|[a-z])\//, // a Unix or Git Bash path
  /\b(sk|pk)-[\w-]{16,}/, // an API key
  /\bBearer\s+\w/, // an authorisation header
];

const games: SiteGame[] = index;

describe.each(games)("the recorded game $file", (game) => {
  const file = resolve(PUBLIC, `.${addressOf(game)}`);
  const review = reviewBeside(file);

  it("is the site's own, played to its end, with its review beside it", () => {
    expect(isSiteGame(addressOf(game))).toBe(true);
    expect(existsSync(review)).toBe(true);
    const events = eventsInGameFile(readFileSync(file, "utf-8"));
    expect(events.at(-1)?.payload.type).toBe("game_ended");
  });

  it("holds nothing from outside the game", () => {
    for (const path of [file, review]) {
      const text = readFileSync(path, "utf-8");
      for (const pattern of OUTSIDE_WORLD) expect(text).not.toMatch(pattern);
    }
  });
});

describe("the games the replay site plays", () => {
  it("are its own only", () => {
    expect(isSiteGame("/site/games/first-game.ndjson")).toBe(true);
    for (const elsewhere of [
      "http://127.0.0.1:8000/games/a1.ndjson",
      "https://example.com/site/games/forged.ndjson",
      "//example.com/site/games/forged.ndjson",
      "/site/games/../../secret.ndjson",
      "/site/games/first-game.json",
      "/a-game.ndjson",
    ]) {
      expect(isSiteGame(elsewhere), elsewhere).toBe(false);
    }
  });
});
