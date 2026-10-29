/**
 * The synthesizer: plays what the Score decides through the Web Audio API, making every sound
 * from oscillators and noise as it plays, so there is nothing to download. Each frame books the
 * music's notes a moment ahead on the audio clock, so a late frame never makes it stutter.
 * Holding suspends the audio clock, which pauses everything at once.
 */
import type { Sounds, Sting, Theme } from "../core/soundtrack";
import { hertzOf, type Loop, STINGS, THEMES, type Wave } from "./music";

/** How far ahead each frame books the music's notes: a few frames' worth. */
const BOOK_AHEAD_SECONDS = 0.15;
/** How long one theme takes to give way to the next. */
const CROSSFADE_SECONDS = 2;
/** The quickest a voice babbles, however fast playback goes. */
const BLIP_GAP_SECONDS = 0.045;
const BLIP_SECONDS = 0.06;
/** A slight lilt from one blip to the next, so a voice is not one flat note. */
const LILT = [1, 1.06, 0.97, 1.03];
/** How loud each kind of sound peaks, before the Spectator's volume. */
const LEVELS = { sting: 0.14, noise: 0.3, blip: 0.06 };
/** How quickly a note rises to its peak: fast enough to sound struck, slow enough not to click. */
const ATTACK_SECONDS = 0.005;
/** Where a note's fall ends: a fall that halves at a steady rate can never reach zero itself. */
const SILENT = 0.0001;
/** How much of its step a theme's note lasts, so notes on neighbouring steps stay apart. */
const NOTE_SHARE = 0.9;
/** How quickly a sting fades when the next cuts it short. */
const CUT_SHORT_SECONDS = 0.02;
/** How quickly the volume follows the slider, so a change never clicks. */
const VOLUME_SMOOTHING_SECONDS = 0.05;

/** A theme playing, or fading out until `endsAt`. */
interface Track {
  theme: Theme;
  loop: Loop;
  gain: GainNode;
  step: number;
  nextAt: number;
  endsAt: number | null;
}

/** A synthesizer, if the browser can make sound. Browsers let a page start sound only in answer
 * to a click or a key, so make it then. */
export function startSynth(): Synth | null {
  return typeof AudioContext === "undefined" ? null : new Synth(new AudioContext());
}

export class Synth {
  private readonly master: GainNode;
  private readonly noise: AudioBuffer;
  private tracks: Track[] = [];
  private lastBlipAt = -Infinity;
  private blips = 0;
  private held = false;
  /** The sting sounding, so the next can cut it short: one at a time, however fast playback goes. */
  private ringing: GainNode | null = null;

  constructor(private readonly context: AudioContext) {
    this.master = context.createGain();
    this.master.connect(context.destination);
    this.noise = whiteNoise(context);
  }

  setVolume(volume: number): void {
    this.master.gain.setTargetAtTime(volume, this.context.currentTime, VOLUME_SMOOTHING_SECONDS);
  }

  /** Asks the audio clock to stop or go on only when that changes: each ask is a trip to the browser's audio. */
  hold(held: boolean): void {
    if (held === this.held) return;
    this.held = held;
    void (held ? this.context.suspend() : this.context.resume());
  }

  /** At a click, touch or key: a browser may hold back audio started by a gesture it did not count. */
  wake(): void {
    if (!this.held && this.context.state === "suspended") void this.context.resume();
  }

  /** A frame's sounds. */
  play({ theme, sting, blip }: Sounds): void {
    this.setTheme(theme);
    this.book();
    if (sting) this.sting(sting);
    if (blip !== null) this.blip(blip);
  }

  close(): void {
    void this.context.close();
  }

  /** The theme playing fades out as the new one fades in. */
  private setTheme(theme: Theme | null): void {
    const now = this.context.currentTime;
    const playing = this.tracks.find((track) => track.endsAt === null);
    if (playing?.theme === theme) return;
    if (playing) {
      fade(playing.gain, 0, now);
      playing.endsAt = now + CROSSFADE_SECONDS;
    }
    if (!theme) return;
    const gain = this.context.createGain();
    gain.gain.value = 0;
    gain.connect(this.master);
    fade(gain, 1, now);
    this.tracks.push({ theme, loop: THEMES[theme], gain, step: 0, nextAt: now, endsAt: null });
  }

  /** Books each theme's notes up to a moment ahead, and lets go of themes that have faded out. */
  private book(): void {
    const now = this.context.currentTime;
    for (const track of this.tracks.filter(({ endsAt }) => endsAt !== null && endsAt <= now)) track.gain.disconnect();
    this.tracks = this.tracks.filter(({ endsAt }) => endsAt === null || endsAt > now);
    for (const track of this.tracks) {
      track.nextAt = Math.max(track.nextAt, now); // after a stall, carry on rather than catch up
      while (track.nextAt < now + BOOK_AHEAD_SECONDS) {
        for (const { wave, gain, notes } of track.loop.parts) {
          const note = notes[track.step % notes.length];
          if (note != null) this.tone(track.gain, note, wave, gain, track.nextAt, track.loop.stepSeconds * NOTE_SHARE);
        }
        track.step += 1;
        track.nextAt += track.loop.stepSeconds;
      }
    }
  }

  private sting(sting: Sting): void {
    const now = this.context.currentTime;
    this.ringing?.gain.setTargetAtTime(0, now, CUT_SHORT_SECONDS);
    const ringing = this.context.createGain();
    ringing.connect(this.master);
    this.ringing = ringing;
    const { tones, noiseSeconds } = STINGS[sting];
    for (const { at, note, seconds, wave } of tones) this.tone(ringing, note, wave, LEVELS.sting, now + at, seconds);
    if (noiseSeconds > 0) this.burst(ringing, now, noiseSeconds);
  }

  private blip(note: number): void {
    const now = this.context.currentTime;
    if (now - this.lastBlipAt < BLIP_GAP_SECONDS) return;
    this.lastBlipAt = now;
    this.blips += 1;
    const lilt = LILT[this.blips % LILT.length] ?? 1;
    this.tone(this.master, note, "square", LEVELS.blip, now, BLIP_SECONDS, lilt);
  }

  /** One note, a MIDI number bent by `bend`: a quick rise, then a fall to silence over its length. */
  private tone(to: AudioNode, note: number, wave: Wave, peak: number, at: number, seconds: number, bend = 1): void {
    const oscillator = this.context.createOscillator();
    oscillator.type = wave;
    oscillator.frequency.value = hertzOf(note) * bend;
    oscillator.connect(envelope(this.context, peak, at, seconds)).connect(to);
    oscillator.start(at);
    oscillator.stop(at + seconds);
  }

  private burst(to: AudioNode, at: number, seconds: number): void {
    const source = this.context.createBufferSource();
    source.buffer = this.noise;
    source.connect(envelope(this.context, LEVELS.noise, at, seconds)).connect(to);
    source.start(at);
    source.stop(at + seconds);
  }
}

function envelope(context: AudioContext, peak: number, at: number, seconds: number): GainNode {
  const gain = context.createGain();
  gain.gain.setValueAtTime(0, at);
  gain.gain.linearRampToValueAtTime(peak, at + ATTACK_SECONDS);
  gain.gain.exponentialRampToValueAtTime(SILENT, at + seconds);
  return gain;
}

function fade(gain: GainNode, to: number, now: number): void {
  gain.gain.cancelScheduledValues(now);
  gain.gain.setValueAtTime(gain.gain.value, now);
  gain.gain.linearRampToValueAtTime(to, now + CROSSFADE_SECONDS);
}

/** A second of white noise, for shots and thuds. */
function whiteNoise(context: AudioContext): AudioBuffer {
  const buffer = context.createBuffer(1, context.sampleRate, context.sampleRate);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
  return buffer;
}
