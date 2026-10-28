import type { PlaybackView } from "../src/ui/usePlayback";

/** A playback holding at `shown` of the `received` events, doing nothing when asked unless `changes` say otherwise. */
export function playbackAt(shown: number, received: number, changes: Partial<PlaybackView> = {}): PlaybackView {
  const nothing = () => undefined;
  return {
    shown,
    behind: received - shown,
    speed: 1,
    held: true,
    live: false,
    cuts: 0,
    play: nothing,
    hold: nothing,
    next: nothing,
    previous: nothing,
    seek: nothing,
    setSpeed: nothing,
    skipToLive: nothing,
    setWaitForAnimations: nothing,
    animated: nothing,
    ...changes,
  };
}
