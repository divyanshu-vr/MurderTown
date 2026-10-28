/** Asks the server what a game's model calls have cost so far. */
import type { CostReport } from "../protocol";
import { API_URL } from "./followGame";

export type CostSource = () => Promise<CostReport>;

/** A `CostSource` for one game. Only full scope may ask, so only a full-scope page gets one. */
export function costSource(gameId: string, apiUrl = API_URL): CostSource {
  return async () => {
    const response = await fetch(`${apiUrl}/games/${gameId}/cost`);
    if (!response.ok) throw new Error(`The server could not say what the game cost (${response.status}).`);
    return (await response.json()) as CostReport;
  };
}
