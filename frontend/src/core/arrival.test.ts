/** Seam 3 (unit): what the follower keeps of each event that arrives, so what is held stays ordered and gap-free. */
import { describe, expect, it } from "vitest";

import { accept } from "./arrival";

describe("accepting an event", () => {
  it("takes the next one", () => {
    expect(accept(4, 5, true)).toBe("new");
  });

  it("drops one already held, as a reconnect's backlog may send again", () => {
    expect(accept(4, 4, true)).toBe("duplicate");
    expect(accept(4, 2, false)).toBe("duplicate");
  });

  it("notices a gap in full scope, where every event is sent", () => {
    expect(accept(4, 6, true)).toBe("gap");
  });

  it("allows gaps in public scope, where the town's unseen events are left out", () => {
    expect(accept(4, 9, false)).toBe("new");
  });
});
