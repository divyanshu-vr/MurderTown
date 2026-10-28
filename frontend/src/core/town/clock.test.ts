/** Seam 3 (unit): how much of the game's time a frame of real time lasts in town. */
import { describe, expect, it } from "vitest";

import { gameTime } from "./clock";

describe("the town's clock", () => {
  it("runs at playback's speed, slower in slow motion, and stands still while stopped", () => {
    expect(gameTime(100, { speed: 1, stopped: false, slowMotion: false })).toBe(100);
    expect(gameTime(100, { speed: 4, stopped: false, slowMotion: false })).toBe(400);
    expect(gameTime(100, { speed: 1, stopped: false, slowMotion: true })).toBe(30);
    expect(gameTime(100, { speed: 8, stopped: true, slowMotion: false })).toBe(0);
  });
});
