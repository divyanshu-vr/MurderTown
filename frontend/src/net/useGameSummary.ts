import { useCallback, useEffect, useState } from "react";

import { isOver } from "../core/gameView";
import type { GameSummary } from "../protocol";
import { Refusal } from "./fetchJson";
import { gameSummary } from "./games";

const EVERY_MS = 2000;

/**
 * A game at a glance, asked for again every couple of seconds while it is being played.
 * Pausing is not an event, so this is how everyone watching learns a game is paused.
 * `show` puts in a newer summary straight away, such as the one a Host control answers with.
 * An ask the server refuses (a wrong Host token, no such game) is not asked again.
 */
export function useGameSummary(
  gameId: string,
  hostToken: string | null,
): { summary: GameSummary | null; show: (summary: GameSummary) => void } {
  const [summary, show] = useState<GameSummary | null>(null);
  const [refused, setRefused] = useState(false);
  const ask = useCallback(() => {
    gameSummary(gameId, hostToken)
      .then(show)
      .catch((error: unknown) => {
        if (error instanceof Refusal) setRefused(true); // otherwise the last summary stays
      });
  }, [gameId, hostToken]);
  const playing = summary === null || !isOver(summary.status);

  useEffect(ask, [ask]);
  useEffect(() => {
    if (!playing || refused) return;
    const timer = setInterval(ask, EVERY_MS);
    return () => clearInterval(timer);
  }, [ask, playing, refused]);

  return { summary, show };
}
