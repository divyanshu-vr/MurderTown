/** Asks the server for the decision behind an event: every model attempt and any fallback. */
import type { Explanation } from "../protocol";
import { API_URL } from "./followGame";

export type Explain = (seq: number) => Promise<Explanation>;

/** An `Explain` for one game. Only full scope may ask, which the console checks before offering it. */
export function explainer(gameId: string, apiUrl = API_URL): Explain {
  return async (seq) => {
    const response = await fetch(`${apiUrl}/games/${gameId}/events/${seq}/explain`);
    if (!response.ok) throw new Error(`The server could not explain event ${seq} (${response.status}).`);
    return (await response.json()) as Explanation;
  };
}
