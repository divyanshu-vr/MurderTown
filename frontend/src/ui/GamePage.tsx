import { useMemo } from "react";

import { endsTheGame } from "../core/gameView";
import { costSource } from "../net/cost";
import { explainer } from "../net/explain";
import { controlGame } from "../net/games";
import { fileReviewSource, type ReviewSource, reviewSource } from "../net/review";
import { type EventSource, fileSource, liveSource, replaySource, type Scope } from "../net/sources";
import { useEventSource } from "../net/useEventSource";
import { useGameSummary } from "../net/useGameSummary";
import { useReview } from "../net/useReview";
import { GameConsole } from "./GameConsole";
import { HostControls } from "./HostControls";
import { replayPath } from "./paths";
import { usePlayback } from "./usePlayback";

/** A console played back from a source (live follows live, a replay starts at the beginning),
 * with its post-game review once the game has ended, if there is a review to be had. */
function useWatched(source: EventSource, live: boolean, reviews: ReviewSource | undefined) {
  const { events, connection } = useEventSource(source);
  const playback = usePlayback(events, live);
  const last = events.at(-1);
  const review = useReview(reviews, last !== undefined && endsTheGame(last));
  return { events, connection, playback, review };
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
  const reviews = useMemo(() => (host ? reviewSource(gameId, host) : undefined), [gameId, host]);
  const { events, connection, playback, review } = useWatched(source, !replay, reviews);
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
      review={review}
    />
  );
}

/** A game file replayed with no server: everything the events hold, and the review beside it. */
export function GameFilePage({ file }: { file: string }) {
  const source = useMemo(() => fileSource(file), [file]);
  const reviews = useMemo(() => fileReviewSource(file), [file]);
  const { events, connection, playback, review } = useWatched(source, false, reviews);
  return <GameConsole events={events} connection={connection} playback={playback} review={review} />;
}
