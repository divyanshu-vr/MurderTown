import { useEffect, useRef, useState } from "react";

import type { GameView } from "../core/gameView";
import { Soundtrack } from "../core/soundtrack";
import type { Event } from "../protocol";
import { startSynth, type Synth } from "../sound/synth";
import { deterministic } from "./motion";
import type { PlaybackView } from "./usePlayback";

/** Whether the game is heard, and how loud: the Spectator's choice, which the browser remembers. */
interface SoundChoice {
  on: boolean;
  volume: number;
}

export interface SoundControls extends SoundChoice {
  setOn(on: boolean): void;
  setVolume(volume: number): void;
}

const KEY = "murdertown.sound";
const UNTOUCHED: SoundChoice = { on: true, volume: 0.6 };

/**
 * The game's music, voices and stings, following playback: each animation frame the Soundtrack
 * says what to sound for the events shown, and the synthesizer plays it. Sound starts at the
 * Spectator's first click, touch or key, as browsers require, and never in a deterministic run.
 */
export function useSound(
  events: readonly Event[],
  view: GameView,
  playback: PlaybackView | undefined,
  mystery: boolean,
): SoundControls {
  const [choice, setChoice] = useState(heldChoice);
  const [soundtrack] = useState(() => new Soundtrack());
  const synth = useRef<Synth | null>(null);
  const loudness = useRef(0);
  const latest = useRef({ events, view, playback, mystery });

  useEffect(() => {
    latest.current = { events, view, playback, mystery };
  });

  useEffect(() => {
    keepChoice(choice);
    loudness.current = choice.on ? choice.volume : 0;
    synth.current?.setVolume(loudness.current);
  }, [choice]);

  useEffect(() => {
    if (deterministic()) return;
    const start = () => {
      if (!synth.current) {
        synth.current = startSynth();
        synth.current?.setVolume(loudness.current);
      }
      synth.current?.wake();
    };
    const gestures = ["pointerdown", "pointerup", "keydown"]; // a touch counts only as it ends
    for (const gesture of gestures) window.addEventListener(gesture, start);
    return () => {
      for (const gesture of gestures) window.removeEventListener(gesture, start);
      synth.current?.close();
      synth.current = null;
    };
  }, []);

  useEffect(() => {
    let frame = 0;
    const onFrame = () => {
      const { events, view, playback, mystery } = latest.current;
      if (playback) {
        const { cuts, held, sinceShown } = playback;
        const sounds = soundtrack.next({ events, view, cuts, held, mystery, sinceShown });
        synth.current?.hold(held);
        synth.current?.play(sounds);
      }
      frame = requestAnimationFrame(onFrame);
    };
    frame = requestAnimationFrame(onFrame);
    return () => cancelAnimationFrame(frame);
  }, [soundtrack]);

  return {
    ...choice,
    setOn: (on) => setChoice((now) => ({ ...now, on })),
    setVolume: (volume) => setChoice((now) => ({ ...now, volume })),
  };
}

/** Storage may be blocked, so every read and write may fail quietly, leaving the defaults. */
function heldChoice(): SoundChoice {
  try {
    const held: unknown = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (typeof held !== "object" || held === null) return UNTOUCHED;
    const { on, volume } = held as Partial<SoundChoice>;
    return {
      on: typeof on === "boolean" ? on : UNTOUCHED.on,
      volume: typeof volume === "number" ? Math.min(Math.max(volume, 0), 1) : UNTOUCHED.volume,
    };
  } catch {
    return UNTOUCHED;
  }
}

function keepChoice(choice: SoundChoice): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(choice));
  } catch {
    // not remembered, then
  }
}
