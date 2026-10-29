/** The setup form checks numbers against the protocol the server validates with, so the two agree. */
import { describe, expect, it } from "vitest";

import { boundsOf, defaultConfig, problemsWith } from "./setup";

describe("setting up a game", () => {
  it("bounds each number as the server does", () => {
    expect(boundsOf("residents")).toEqual({ min: 6, max: 15, whole: true, optional: false });
    expect(boundsOf("detective_accuracy")).toEqual({ min: 0.5, max: 1, whole: false, optional: false });
    expect(boundsOf("open_floor_seconds")).toEqual({ min: 10, max: 3600, whole: true, optional: true });
  });

  it("starts from the server's defaults, with no seed, so the server draws one", () => {
    const config = defaultConfig();

    expect(config).toMatchObject({ residents: 12, murderers: 2, max_days: 10, open_floor_seconds: 180 });
    expect(config.lineup?.everyone?.provider).toBe("scripted");
    expect(config).not.toHaveProperty("seed");
  });

  it("names every number out of bounds", () => {
    const config = { ...defaultConfig(), residents: 20, murderers: 0, max_days: 2.5, detective_accuracy: 0.75 };

    expect(problemsWith(config)).toEqual({ residents: "at most 15", murderers: "at least 1", max_days: "a whole number" });
  });

  it("allows the Open floor no time limit, but every other number must be given", () => {
    expect(problemsWith({ ...defaultConfig(), open_floor_seconds: null })).toEqual({});
    expect(problemsWith({ ...defaultConfig(), residents: Number.NaN })).toEqual({ residents: "a number" });
  });
});
