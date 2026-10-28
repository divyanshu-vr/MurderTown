/**
 * Playback: how a Spectator moves through what has arrived, at their own pace or following
 * live. Pure, with no timers: a hook feeds it each animation frame's time, and tests feed it
 * numbers. It counts the cuts, the times the view jumps rather than plays on, so the town can
 * snap to a jump instead of walking there.
 *
 * Time here is the game's virtual time: real time times the speed, standing still while held.
 * Each event stays shown for its dwell (presentation.ts) before the next appears, and a
 * blocking one also waits for its animation to finish, a few seconds at most. While following
 * live, falling more than a minute behind jumps to live; a Spectator who chose their own pace
 * (held, moved an event at a time, sought or changed speed) is left alone until they skip to
 * live, or reach the live edge while playing. Mystery mode is only a way of showing what is
 * shown, so playback does not know about it.
 */
import type { Event } from "../protocol";
import { blocks, dwellOf } from "./presentation";

export const SPEEDS = [0.5, 1, 2, 4, 8] as const;
export type Speed = (typeof SPEEDS)[number];

/** Falling further behind than this, while following live, jumps to live. */
export const CATCH_UP_MS = 60_000;

/** The longest a blocking moment waits for its animation. */
export const ANIMATION_TIMEOUT_MS = 4000;

/** The most real time one animation frame counts, so a tab left hidden does not leap ahead. */
export const MAX_FRAME_MS = 250;

/** The speed one notch slower (-1) or faster (1), staying within the speeds on offer. */
export function nextSpeed(speed: Speed, notches: -1 | 1): Speed {
  const index = SPEEDS.indexOf(speed) + notches;
  return SPEEDS[Math.min(Math.max(index, 0), SPEEDS.length - 1)] ?? speed;
}

export interface PlaybackOptions {
  /** Following a game live, so falling far behind jumps to live. A replay starts at the beginning. */
  live: boolean;
}

export class Playback {
  /** How many of the events received are shown. */
  shown = 0;
  speed: Speed = 1;
  held = false;
  /** Whether the Spectator chose their own pace, so falling behind does not jump to live. */
  detached: boolean;
  /** How many times the view has jumped: sought, stepped back, or skipped or caught up to live. */
  cuts = 0;

  private events: readonly Event[] = [];
  /** How many events had arrived when last told: a caller may add to the same list. */
  private received = 0;
  private now = 0;
  /** When the latest event shown appeared, in virtual time. */
  private shownAt = 0;
  /** Whether a blocking moment waits for its animation: only while something animates it. */
  private waitForAnimations = false;
  /** The blocking event shown last, while its animation is still playing. */
  private animating: number | null = null;
  /** When the latest event's animation finished, so the next one still gets its full time. */
  private animatedAt = 0;

  constructor({ live }: PlaybackOptions) {
    this.detached = !live;
  }

  /** Events received but not shown yet. */
  get behind(): number {
    return this.events.length - this.shown;
  }

  /** Everything received so far, in order; it only ever grows. */
  receive(events: readonly Event[]): void {
    const idle = this.shown === this.received;
    this.events = events;
    this.received = events.length;
    const latest = this.latestShown();
    if (idle && latest) {
      // after a quiet spell, the next event appears at once rather than in a burst of overdue ones
      this.shownAt = Math.max(this.shownAt, this.now - dwellOf(latest));
    }
    if (!this.detached && this.timeToCatchUp() > CATCH_UP_MS) this.jumpToLive();
  }

  /** One animation frame's real time, counted up to a quarter second. */
  frame(realMs: number): void {
    this.tick(Math.min(realMs, MAX_FRAME_MS));
  }

  /** Let `realMs` of real time pass. */
  tick(realMs: number): void {
    if (this.held) return;
    this.now += realMs * this.speed;
    for (;;) {
      const latest = this.latestShown();
      if (latest && this.animating === latest.seq) {
        if (this.waitForAnimations && this.now - this.shownAt < ANIMATION_TIMEOUT_MS) return;
        this.animated(latest.seq, Math.min(this.now, this.shownAt + ANIMATION_TIMEOUT_MS));
      }
      const due = latest ? Math.max(this.shownAt + dwellOf(latest), this.animatedAt) : this.shownAt;
      if (this.shown >= this.events.length || this.now < due) return;
      this.showNext(due);
    }
  }

  /** A blocking moment's animation has finished. */
  animated(seq: number, at = this.now): void {
    if (this.animating !== seq) return;
    this.animating = null;
    this.animatedAt = at;
  }

  play(): void {
    this.held = false;
    this.followIfAtTheEdge();
  }

  hold(): void {
    this.held = true;
    this.detached = true;
  }

  setWaitForAnimations(on: boolean): void {
    this.waitForAnimations = on;
  }

  setSpeed(speed: Speed): void {
    this.speed = speed;
    this.detached = true;
  }

  /** Show one more event, then hold. */
  next(): void {
    this.stayHere();
    if (this.shown < this.events.length) this.showNext(this.now);
  }

  /** Show one event fewer, then hold. */
  previous(): void {
    this.stayHere();
    this.cuts += 1;
    this.shown = Math.max(0, this.shown - 1);
  }

  /** Show the first `count` events. */
  seek(count: number): void {
    this.detached = true;
    this.cuts += 1;
    this.animating = null;
    this.shown = Math.min(Math.max(0, count), this.events.length);
    this.shownAt = this.now;
    this.followIfAtTheEdge();
  }

  skipToLive(): void {
    this.held = false;
    this.jumpToLive();
  }

  /** Hold where playback is, as the Spectator chose. */
  private stayHere(): void {
    this.held = true;
    this.detached = true;
    this.animating = null;
    this.shownAt = this.now;
  }

  private jumpToLive(): void {
    this.detached = false;
    this.cuts += 1;
    this.animating = null;
    this.shown = this.events.length;
    this.shownAt = this.now;
  }

  private showNext(at: number): void {
    const next = this.events[this.shown];
    if (!next) return;
    this.shown += 1;
    this.shownAt = at;
    this.animatedAt = 0;
    this.animating = this.waitForAnimations && blocks(next) ? next.seq : null;
    this.followIfAtTheEdge();
  }

  /** Playing at the live edge follows live again, whatever pace was chosen to get there. */
  private followIfAtTheEdge(): void {
    if (!this.held && this.shown === this.events.length) this.detached = false;
  }

  private latestShown(): Event | undefined {
    return this.events[this.shown - 1];
  }

  /** How long showing everything received would take at normal speed. */
  private timeToCatchUp(): number {
    const waiting = this.events.slice(Math.max(this.shown - 1, 0), -1);
    return waiting.reduce((total, event) => total + dwellOf(event), 0);
  }
}
