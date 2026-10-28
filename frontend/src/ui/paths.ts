/** Where each game can be watched: live, or replayed from its start. */
export function gamePath(gameId: string): string {
  return `/games/${gameId}`;
}

export function replayPath(gameId: string): string {
  return `${gamePath(gameId)}/replay`;
}

/** A game's id, and whether it is to be replayed, from a page's path. */
export function gameAt(path: string): { gameId: string; replay: boolean } | null {
  const found = /^\/games\/([0-9a-f]+)(\/replay)?\/?$/.exec(path);
  return found?.[1] ? { gameId: found[1], replay: Boolean(found[2]) } : null;
}

/** Where a game file is replayed with no server, from the start or in mystery mode. */
export function gameFilePath(file: string, mystery = false): string {
  const asked = new URLSearchParams({ file });
  if (mystery) asked.set("mystery", "1");
  return `/replay?${asked.toString()}`;
}

/** The game file a page replays, and whether in mystery mode, from its address. */
export function gameFileAt(address: URL | Location): { file: string; mystery: boolean } | null {
  const asked = new URLSearchParams(address.search);
  const file = asked.get("file");
  if (address.pathname !== "/replay" || !file) return null;
  return { file, mystery: asked.get("mystery") === "1" };
}
