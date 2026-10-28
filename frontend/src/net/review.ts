import type { Review } from "../protocol";
import { API_URL, fetchJson } from "./fetchJson";

/** Asks for a game's post-game review; null when there is none to be had. */
export type ReviewSource = () => Promise<Review | null>;

/** The server's review of a game. Only the Host may ask: it tells private beliefs. */
export function reviewSource(gameId: string, hostToken: string, apiUrl = API_URL): ReviewSource {
  return () => fetchJson<Review>(`${apiUrl}/games/${gameId}/review`, "review the game", { hostToken });
}

/** The review written beside a game file (`<name>.review.json`); a game file without one has none. */
export function fileReviewSource(file: string): ReviewSource {
  return async () => {
    const url = new URL(file, window.location.href);
    url.pathname = url.pathname.replace(/\.ndjson$/, ".review.json");
    try {
      const response = await fetch(url);
      return response.ok ? ((await response.json()) as Review) : null;
    } catch {
      return null;
    }
  };
}
