/** Asks the server about games: the list, one game at a glance, and, as the Host, starting and controlling them. */
import type { Control, GameConfigInput, GameCreated, GameList, GameSummary, SetupChoices } from "../protocol";
import { API_URL, fetchJson } from "./fetchJson";

export async function listGames(hostToken: string | null, apiUrl = API_URL): Promise<GameSummary[]> {
  const list = await fetchJson<GameList>(`${apiUrl}/games`, "list the games", { hostToken });
  return list.games;
}

export function gameSummary(gameId: string, hostToken: string | null, apiUrl = API_URL): Promise<GameSummary> {
  return fetchJson<GameSummary>(`${apiUrl}/games/${gameId}`, "say how the game stands", { hostToken });
}

export function controlGame(gameId: string, control: Control, hostToken: string, apiUrl = API_URL): Promise<GameSummary> {
  return fetchJson<GameSummary>(`${apiUrl}/games/${gameId}/${control}`, `${control} the game`, {
    method: "POST",
    hostToken,
  });
}

export async function startGame(config: GameConfigInput, hostToken: string, apiUrl = API_URL): Promise<string> {
  const started = await fetchJson<GameCreated>(`${apiUrl}/games`, "start the game", {
    method: "POST",
    body: config,
    hostToken,
  });
  return started.id;
}

export function setupChoices(apiUrl = API_URL): Promise<SetupChoices> {
  return fetchJson<SetupChoices>(`${apiUrl}/setup-choices`, "list the providers and models");
}
