import { useMemo } from "react";

import { costSource } from "../net/cost";
import { explainer } from "../net/explain";
import type { Scope } from "../net/followGame";
import { controlGame } from "../net/games";
import { useFollowedGame } from "../net/useFollowedGame";
import { useGameSummary } from "../net/useGameSummary";
import { GameConsole } from "./GameConsole";
import { HostControls } from "./HostControls";

/**
 * One game, followed live. The Host sees it in full scope, with the Mind inspector, the cost
 * meter and the controls; everyone else, and the Host asking for `?scope=public`, in public scope.
 */
export function LiveGamePage({ gameId, hostToken }: { gameId: string; hostToken: string | null }) {
  const publicAsked = new URLSearchParams(window.location.search).get("scope") === "public";
  const host = publicAsked ? null : hostToken;
  const scope: Scope = host ? "full" : "public";
  const { events, connection } = useFollowedGame(gameId, host);
  const { summary, show } = useGameSummary(gameId, host);
  const asks = useMemo(
    () => (host ? { explain: explainer(gameId, host), cost: costSource(gameId, host) } : {}),
    [gameId, host],
  );
  const controls = host && summary && (
    <HostControls offered={summary.controls} onControl={(control) => controlGame(gameId, control, host).then(show)} />
  );
  return (
    <GameConsole
      events={events}
      connection={connection}
      {...asks}
      scope={scope}
      paused={summary?.status === "paused"}
      controls={controls}
    />
  );
}
