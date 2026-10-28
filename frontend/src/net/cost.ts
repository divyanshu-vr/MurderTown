/** Asks the server what a game's model calls have cost so far. */
import type { CostReport } from "../protocol";
import { API_URL, fetchJson } from "./fetchJson";

export type CostSource = () => Promise<CostReport>;

/** A `CostSource` for one game. Only the Host may ask, so only the Host's page gets one. */
export function costSource(gameId: string, hostToken: string, apiUrl = API_URL): CostSource {
  return () => fetchJson<CostReport>(`${apiUrl}/games/${gameId}/cost`, "say what the game cost", { hostToken });
}
