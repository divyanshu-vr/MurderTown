import { useCallback, useEffect, useReducer, useState } from "react";

import { Playback, type SinceShown, type Speed } from "../core/playback";
import type { Event } from "../protocol";

/** Where playback stands, and what the Spectator can do with it. */
export interface PlaybackView {
  /** How many of the events received are shown. */
  shown: number;
  behind: number;
  speed: Speed;
  /** How fast game time runs: the speed chosen, quickened while catching up with live. */
  pace: number;
  /** Whether playback goes noticeably faster than chosen, to catch up with live. */
  catchingUp: boolean;
  /** How long ago, as of now, an event was shown. */
  sinceShown: SinceShown;
  held: boolean;
  /** Following a game live, rather than replaying it. */
  live: boolean;
  /** How many times the view has jumped rather than played on. */
  cuts: number;
  play(): void;
  hold(): void;
  next(): void;
  previous(): void;
  seek(count: number): void;
  setSpeed(speed: Speed): void;
  skipToLive(): void;
  /** Whether blocking moments wait for their animation: while the town is there to play them. */
  setWaitForAnimations(on: boolean): void;
  /** A blocking moment's animation has finished. */
  animated(seq: number): void;
}

/**
 * Plays back the events received, one animation frame at a time. A live game follows live;
 * a replay starts at the beginning. Blocking moments wait for their animation only while the
 * town says it plays them.
 */
export function usePlayback(events: readonly Event[], live: boolean): PlaybackView {
  const [playback] = useState(() => new Playback({ live }));
  const [, rerender] = useReducer((renders: number) => renders + 1, 0);
  // the town holds on to these, so they keep their identity from one render to the next
  const setWaitForAnimations = useCallback((on: boolean) => playback.setWaitForAnimations(on), [playback]);
  const animated = useCallback((seq: number) => playback.animated(seq), [playback]);

  useEffect(() => {
    playback.receive(events);
    rerender();
  }, [playback, events]);

  useEffect(() => {
    let frame = 0;
    let last = performance.now();
    const onFrame = (time: number) => {
      const shown = playback.shown;
      playback.frame(time - last);
      last = time;
      if (playback.shown !== shown) rerender();
      frame = requestAnimationFrame(onFrame);
    };
    frame = requestAnimationFrame(onFrame);
    return () => cancelAnimationFrame(frame);
  }, [playback]);

  const act =
    <A extends unknown[]>(change: (...args: A) => void) =>
    (...args: A) => {
      change(...args);
      rerender();
    };
  return {
    shown: playback.shown,
    behind: playback.behind,
    speed: playback.speed,
    pace: playback.pace,
    catchingUp: playback.catchingUp,
    sinceShown: (seq: number) => playback.sinceShown(seq),
    held: playback.held,
    live,
    cuts: playback.cuts,
    play: act(() => playback.play()),
    hold: act(() => playback.hold()),
    next: act(() => playback.next()),
    previous: act(() => playback.previous()),
    seek: act((count: number) => playback.seek(count)),
    setSpeed: act((speed: Speed) => playback.setSpeed(speed)),
    skipToLive: act(() => playback.skipToLive()),
    setWaitForAnimations,
    animated,
  };
}
