import type { Page } from "@playwright/test";

/** Where the built console looks for the server (its default `API_URL`). */
export const API = "http://127.0.0.1:8000";

/** Serve the recorded game as a game file, with its review beside it and no server at all; returns the page that replays it. */
export async function serveTheGameFile(page: Page): Promise<string> {
  await page.route(`${API}/**`, (route) => route.abort()); // the server is gone
  await page.route(({ pathname }) => pathname === "/a-game.ndjson", (route) =>
    route.fulfill({ path: "../fixtures/scripted-game.ndjson" }),
  );
  await page.route(({ pathname }) => pathname === "/a-game.review.json", (route) =>
    route.fulfill({ path: "../fixtures/scripted-game.review.json" }),
  );
  return "/replay?file=/a-game.ndjson";
}

/** Browse as a browser without WebGL does: canvases offer no WebGL context. */
export async function withoutWebGL(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, kind: string, options?: unknown) {
      return kind.startsWith("webgl") ? null : getContext.call(this, kind, options);
    } as typeof getContext;
  });
}
