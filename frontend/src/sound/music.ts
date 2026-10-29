/**
 * The notes the synthesizer plays: the day and night themes, and each sting. Notes are MIDI
 * numbers (60 is middle C); a theme is a loop of steps, with null for a rest.
 */
import type { Sting, Theme } from "../core/soundtrack";

/** A sound wave a note is played with: the square's buzz, the triangle's softer hum. */
export type Wave = "square" | "triangle";

export interface Part {
  wave: Wave;
  gain: number;
  notes: readonly (number | null)[];
}

export interface Loop {
  /** How long each step lasts. */
  stepSeconds: number;
  parts: readonly Part[];
}

export interface Tone {
  /** When it sounds, after the sting starts. */
  at: number;
  note: number;
  seconds: number;
  wave: Wave;
}

export interface StingNotes {
  tones: readonly Tone[];
  /** A burst of noise, as of a shot, lasting this long; 0 for none. */
  noiseSeconds: number;
}

/** Eight steps to a bar, four bars to a loop. */
const bars = (...steps: (number | null)[][]) => steps.flat();

export const THEMES: Record<Theme, Loop> = {
  // C, A minor, F, G: a bright stroll round the square
  day: {
    stepSeconds: 60 / 112 / 2,
    parts: [
      {
        wave: "square",
        gain: 0.05,
        notes: bars(
          [76, null, 79, null, 84, null, 79, 76],
          [69, null, 72, null, 76, null, 72, 69],
          [65, null, 69, null, 72, null, 77, 76],
          [74, null, 71, null, 67, null, 71, null],
        ),
      },
      {
        wave: "triangle",
        gain: 0.16,
        notes: bars(
          [48, null, 55, null, 48, null, 55, null],
          [45, null, 52, null, 45, null, 52, null],
          [41, null, 48, null, 41, null, 48, null],
          [43, null, 50, null, 43, null, 50, null],
        ),
      },
    ],
  },
  // A minor, F, D minor, E: slower, sparser, waiting for someone to knock
  night: {
    stepSeconds: 60 / 76 / 2,
    parts: [
      {
        wave: "triangle",
        gain: 0.12,
        notes: bars(
          [69, null, null, 72, null, null, 76, null],
          [77, null, null, 76, null, null, 72, null],
          [74, null, null, 77, null, null, 81, null],
          [80, null, null, 76, null, null, 71, null],
        ),
      },
      {
        wave: "square",
        gain: 0.03,
        notes: bars(
          [45, null, null, null, 45, null, null, null],
          [41, null, null, null, 41, null, null, null],
          [38, null, null, null, 38, null, null, null],
          [40, null, null, null, 40, null, null, null],
        ),
      },
    ],
  },
};

const tone = (at: number, note: number, seconds: number, wave: Wave = "square"): Tone => ({ at, note, seconds, wave });

export const STINGS: Record<Sting, StingNotes> = {
  phase: { tones: [tone(0, 79, 0.25, "triangle"), tone(0.12, 84, 0.4, "triangle")], noiseSeconds: 0 },
  ballot: { tones: [tone(0, 96, 0.05)], noiseSeconds: 0 },
  "vote-result": { tones: [tone(0, 60, 0.7, "triangle"), tone(0, 64, 0.7, "triangle"), tone(0, 67, 0.7, "triangle")], noiseSeconds: 0 },
  banishment: { tones: [tone(0, 72, 0.15), tone(0.15, 67, 0.15), tone(0.3, 63, 0.15), tone(0.45, 60, 0.6)], noiseSeconds: 0 },
  murder: { tones: [tone(0, 57, 0.7), tone(0, 58, 0.7), tone(0.35, 45, 0.9, "triangle")], noiseSeconds: 0.15 },
  shot: { tones: [tone(0, 31, 0.3, "triangle")], noiseSeconds: 0.3 },
  "town-wins": {
    tones: [tone(0, 60, 0.12), tone(0.12, 64, 0.12), tone(0.24, 67, 0.12), tone(0.36, 72, 0.8), tone(0.36, 76, 0.8, "triangle")],
    noiseSeconds: 0,
  },
  "murderers-win": {
    tones: [tone(0, 69, 0.2), tone(0.2, 65, 0.2), tone(0.4, 62, 0.2), tone(0.6, 56, 1), tone(0.6, 44, 1, "triangle")],
    noiseSeconds: 0,
  },
};

export function hertzOf(note: number): number {
  return 440 * 2 ** ((note - 69) / 12);
}
