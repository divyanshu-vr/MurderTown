import { fetchJson } from "./fetchJson";

/** One game the replay site holds: its game file, from the site's folder, and how the landing
 * page introduces it without giving away who wins. */
export interface SiteGame {
  file: string;
  title: string;
  blurb: string;
}

/** The folder the replay site keeps its games and their list in. */
export const SITE_FOLDER = "/site";

const ITS_OWN = new RegExp(`^${SITE_FOLDER}/games/[\\w-]+\\.ndjson$`);

/** Where a game the replay site holds is served. */
export function addressOf(game: SiteGame): string {
  return `${SITE_FOLDER}/${game.file}`;
}

/** Whether a game file is one the replay site holds. The site plays only these, so no link can
 * make it play a game from anywhere else, or ask a server for one. */
export function isSiteGame(file: string): boolean {
  return ITS_OWN.test(file);
}

export function siteGames(): Promise<SiteGame[]> {
  return fetchJson<SiteGame[]>(`${SITE_FOLDER}/index.json`, "list the recorded games");
}
