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
