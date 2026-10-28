import { useMemo } from "react";

import { costSource } from "../net/cost";
import { explainer } from "../net/explain";
import { controlGame } from "../net/games";
import { type EventSource, fileSource, liveSource, replaySource, type Scope } from "../net/sources";
import { useEventSource } from "../net/useEventSource";
import { useGameSummary } from "../net/useGameSummary";
import { GameConsole } from "./GameConsole";
import { HostControls } from "./HostControls";
import { replayPath } from "./paths";
import { usePlayback } from "./usePlayback";

/** A console played back from a source: live follows live, a replay starts at the beginning. */
function useWatched(source: EventSource, live: boolean) {
  const { events, connection } = useEventSource(source);
  const playback = usePlayback(events, live);
  return { events, connection, playback };
}

/**
 * One game, followed live or replayed from the server. The Host sees it in full scope, with the
 * Mind inspector, the cost meter and the controls; everyone else, and the Host asking for
 * `?scope=public`, in public scope. Once the view reaches the game's end, it offers the replay link.
 */
export function GamePage({ gameId, hostToken, replay }: { gameId: string; hostToken: string | null; replay: boolean }) {
  const publicAsked = new URLSearchParams(window.location.search).get("scope") === "public";
  const host = publicAsked ? null : hostToken;
  const scope: Scope = host ? "full" : "public";
  const source = useMemo(
    () => (replay ? replaySource(gameId, host) : liveSource(gameId, host)),
    [gameId, host, replay],
  );
  const { events, connection, playback } = useWatched(source, !replay);
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
      playback={playback}
      replayUrl={`${window.location.origin}${replayPath(gameId)}`}
    />
  );
}

/** A game file replayed with no server: everything the events hold, nothing more. */
export function GameFilePage({ file }: { file: string }) {
  const source = useMemo(() => fileSource(file), [file]);
  const { events, connection, playback } = useWatched(source, false);
  return <GameConsole events={events} connection={connection} playback={playback} />;
}
