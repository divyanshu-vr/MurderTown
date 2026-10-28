import { useEffect } from "react";

import { nextSpeed, SPEEDS, type Speed } from "../core/playback";
import type { PlaybackView } from "./usePlayback";

const button =
  "rounded-full border border-stone-700 px-3 py-1 text-stone-200 enabled:hover:border-amber-300 disabled:opacity-50";

/**
 * Playback's controls: hold or play, move an event back or forward, the speed, a timeline to scrub,
 * how far behind what has arrived the view is, and a way back to live (or to a replay's end).
 * Once a game is over, a link to share its replay.
 */
export function PlaybackBar({
  playback,
  received,
  replayUrl,
}: {
  playback: PlaybackView;
  received: number;
  replayUrl?: string | undefined;
}) {
  const { shown, behind, speed, held, live } = playback;
  return (
    <div
      role="group"
      aria-label="Playback"
      className="flex flex-wrap items-center gap-3 border-b border-stone-800 px-6 py-2 text-sm"
    >
      <button type="button" className={button} title="←" onClick={playback.previous}>
        Previous event
      </button>
      <button type="button" className={button} title="Space" onClick={held ? playback.play : playback.hold}>
        {held ? "Play" : "Hold"}
      </button>
      <button type="button" className={button} title="→" onClick={playback.next}>
        Next event
      </button>
      <label className="flex items-center gap-2 text-stone-400">
        Speed
        <select
          className="rounded border border-stone-700 bg-stone-900 px-2 py-1 text-stone-100"
          title="Slower (-) or faster (=)"
          value={speed}
          onChange={(event) => playback.setSpeed(Number(event.target.value) as Speed)}
        >
          {SPEEDS.map((choice) => (
            <option key={choice} value={choice}>
              {choice}×
            </option>
          ))}
        </select>
      </label>
      <input
        type="range"
        aria-label="Timeline"
        className="min-w-32 flex-1 accent-amber-300"
        min={0}
        max={received}
        value={shown}
        onChange={(event) => playback.seek(Number(event.target.value))}
      />
      {behind > 0 && (
        <span className="text-stone-400">
          {behind} {behind === 1 ? "event" : "events"} behind
        </span>
      )}
      <button type="button" className={button} title="L" disabled={behind === 0} onClick={playback.skipToLive}>
        {live ? "Skip to live" : "Skip to the end"}
      </button>
      {replayUrl && (
        <a href={replayUrl} className="text-amber-200 hover:underline">
          Replay link
        </a>
      )}
    </div>
  );
}

/** Whether the focused control uses a key itself: typing, choosing from a list, moving a slider
 * with the arrows, or pressing a button with Space. Every other key is playback's. */
function keyBelongsToFocus(target: EventTarget | null, key: string): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return true;
  if (target instanceof HTMLInputElement) {
    return target.type === "range" ? key.startsWith("Arrow") : true;
  }
  return target.tagName === "BUTTON" && (key === " " || key === "Enter");
}

/** Space holds or plays, the arrows move an event back or forward, L skips to live, minus and equals
 * change speed, M toggles mystery mode. */
export function usePlaybackKeys(playback: PlaybackView | undefined, toggleMystery: (() => void) | undefined): void {
  useEffect(() => {
    if (!playback) return;
    const actions: Record<string, () => void> = {
      " ": playback.held ? playback.play : playback.hold,
      ArrowLeft: playback.previous,
      ArrowRight: playback.next,
      l: playback.skipToLive,
      "-": () => playback.setSpeed(nextSpeed(playback.speed, -1)),
      "=": () => playback.setSpeed(nextSpeed(playback.speed, 1)),
      ...(toggleMystery && { m: toggleMystery }),
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || keyBelongsToFocus(event.target, event.key)) return;
      const action = actions[event.key.length === 1 ? event.key.toLowerCase() : event.key];
      if (!action) return;
      event.preventDefault();
      action();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playback, toggleMystery]);
}
