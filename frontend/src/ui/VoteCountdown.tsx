import { useEffect, useReducer } from "react";

import { type OpenFloorClock, openFloorOf } from "../core/openFloor";
import type { Event } from "../protocol";
import type { PlaybackView } from "./usePlayback";

/** How often the countdown is read again while it counts. */
const TICK_MS = 250;

/**
 * How long until the Vote, during the Open floor: the time left, if the game has a limit, and the
 * Statements left. It counts down as playback plays and stands still while it is held.
 */
export function VoteCountdown({
  events,
  playback,
}: {
  events: readonly Event[];
  playback?: Pick<PlaybackView, "sinceShown" | "held"> | undefined;
}) {
  const [, tick] = useReducer((ticks: number) => ticks + 1, 0);
  const clock = openFloorOf(events, playback?.sinceShown);
  const counting = playback !== undefined && !playback.held && (clock?.secondsLeft ?? 0) > 0;

  useEffect(() => {
    if (!counting) return;
    const timer = setInterval(tick, TICK_MS);
    return () => clearInterval(timer);
  }, [counting]);

  if (!clock) return null;
  return (
    <p role="timer" aria-label="Until the Vote" className="text-stone-300">
      {untilTheVote(clock)}
    </p>
  );
}

function untilTheVote({ statementsLeft, secondsLeft }: OpenFloorClock): string {
  const statements = statementsLeft === 1 ? "Statement" : "Statements";
  const due = statementsLeft === 0 || secondsLeft === 0;
  if (secondsLeft === null) return due ? "Vote any moment" : `Vote after ${statementsLeft} more ${statements}`;
  const when = due ? "Vote any moment" : `Vote in ${minutesAndSeconds(secondsLeft)}`;
  return `${when} · ${statementsLeft} ${statements} left`;
}

/** `seconds` as m:ss, rounded up, so the last second shows 0:01 rather than 0:00. */
function minutesAndSeconds(seconds: number): string {
  const whole = Math.ceil(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
