/** Asks the server for the decision behind an event: every model attempt and any fallback. */
import type { Explanation } from "../protocol";
import { API_URL, fetchJson } from "./fetchJson";

export type Explain = (seq: number) => Promise<Explanation>;

/** An `Explain` for one game. Only the Host may ask, so only the Host's page gets one. */
export function explainer(gameId: string, hostToken: string, apiUrl = API_URL): Explain {
  const url = (seq: number) => `${apiUrl}/games/${gameId}/events/${seq}/explain`;
  return (seq) => fetchJson<Explanation>(url(seq), `explain event ${seq}`, { hostToken });
}
