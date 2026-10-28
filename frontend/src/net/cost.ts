/** Asks the server what a game's model calls have cost so far. */
import type { CostReport } from "../protocol";
import { fetchJson } from "./fetchJson";
import { API_URL } from "./followGame";

export type CostSource = () => Promise<CostReport>;

/** A `CostSource` for one game. Only full scope may ask, so only a full-scope page gets one. */
export function costSource(gameId: string, apiUrl = API_URL): CostSource {
  return () => fetchJson<CostReport>(`${apiUrl}/games/${gameId}/cost`, "say what the game cost");
}
