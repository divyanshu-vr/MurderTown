/** The Host token reaches the browser in the link `mm serve` prints, and stays out of the address bar. */
import { afterEach, describe, expect, it } from "vitest";

import { forgetHostToken, heldHostToken, takeHostTokenFromLink } from "./hostToken";

afterEach(() => {
  forgetHostToken();
  window.history.replaceState(null, "", "/");
});

describe("the Host token", () => {
  it("is kept from the link that hands it over, which then leaves the address bar", () => {
    window.history.replaceState(null, "", "/games/abc?scope=public#host-token=s3cret%2Bkey");

    takeHostTokenFromLink();

    expect(heldHostToken()).toBe("s3cret+key");
    expect(window.location.hash).toBe("");
    expect(window.location.pathname + window.location.search).toBe("/games/abc?scope=public");
  });

  it("is not held by a browser that was never handed it", () => {
    takeHostTokenFromLink();

    expect(heldHostToken()).toBeNull();
  });
});
