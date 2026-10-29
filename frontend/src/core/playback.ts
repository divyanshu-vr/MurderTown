/**
 * Playback: how a Spectator moves through what has arrived, at their own pace or following
 * live. Pure, with no timers: a hook feeds it each animation frame's time, and tests feed it
 * numbers. It counts the cuts, the times the view jumps rather than plays on, so the town can
 * snap to a jump instead of walking there.
 *
 * Time here is the game's virtual time: real time times the pace, standing still while held.
 * Each event stays shown for its dwell (presentation.ts) before the next appears, and a
 * blocking one also waits for its animation to finish, a few seconds at most. While following
 * live, falling more than ten seconds behind plays gradually faster, up to three times the
 * chosen speed a minute behind, so every word is still shown. Only skipping to live jumps
 * there, and a live game joined more than a minute along starts at its live edge. A Spectator
 * who chose their own pace (held, moved an event at a time, sought or changed speed) is left
 * alone until they skip to live, or reach the live edge while playing. Mystery mode is only a
 * way of showing what is shown, so playback does not know about it.
 */
import type { Event } from "../protocol";
import { blocks, dwellOf } from "./presentation";

export const SPEEDS = [0.5, 1, 2, 4, 8] as const;
export type Speed = (typeof SPEEDS)[number];

/** How far behind, at normal speed, playback catches up at its fastest. */
export const CATCH_UP_MS = 60_000;

/** How far along a live game must be for a Spectator who joins it to start at its live edge. */
export const JOIN_AT_LIVE_MS = 60_000;

/** How long after the first events arrive the rest still count as the backlog of a game joined:
 * the server sends it an event at a time, so it arrives over a moment, not at once. */
export const JOINING_MS = 2000;

/** The most times faster than the chosen speed playback goes to catch up with live. */
export const MAX_CATCH_UP = 3;

/** Behind by less than this, live playback keeps the chosen speed, as live play always is a little. */
export const CATCH_UP_FROM_MS = 10_000;

/** How much faster than chosen counts as catching up, for the Spectator to be told. */
const NOTICEABLY_FASTER = 1.1;

/** The longest a blocking moment waits for its animation: well past a Night Visit across town and
 * back (visit.test.ts measures the longest), in case the town's clock runs behind playback's. */
export const ANIMATION_TIMEOUT_MS = 12_000;

/** The most real time one animation frame counts, so a tab left hidden does not leap ahead. */
export const MAX_FRAME_MS = 250;

/** The speed one notch slower (-1) or faster (1), staying within the speeds on offer. */
export function nextSpeed(speed: Speed, notches: -1 | 1): Speed {
  const index = SPEEDS.indexOf(speed) + notches;
  return SPEEDS[Math.min(Math.max(index, 0), SPEEDS.length - 1)] ?? speed;
}

export interface PlaybackOptions {
  /** Following a game live, so falling behind catches up. A replay starts at the beginning. */
  live: boolean;
}

export class Playback {
  /** How many of the events received are shown. */
  shown = 0;
  speed: Speed = 1;
  held = false;
  /** Whether the Spectator chose their own pace, so falling behind does not catch up. */
  detached: boolean;
  /** How many times the view has jumped: sought, stepped back, skipped to live or joined there. */
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
  /** How long showing the events from `from` up to `to` would take: what was waiting when last asked. */
  private backlog = { from: 0, to: 0, ms: 0 };
  /** When the first events arrived, in virtual time: until then, nothing has. */
  private firstArrival: number | null = null;

  constructor({ live }: PlaybackOptions) {
    this.detached = !live;
  }

  /** Events received but not shown yet. */
  get behind(): number {
    return this.events.length - this.shown;
  }

  /** How fast game time runs: the chosen speed, quickened while catching up with live. */
  get pace(): number {
    if (this.detached) return this.speed;
    const lag = (this.timeToCatchUp() - CATCH_UP_FROM_MS) / (CATCH_UP_MS - CATCH_UP_FROM_MS);
    return this.speed * (1 + (MAX_CATCH_UP - 1) * Math.min(Math.max(lag, 0), 1));
  }

  /** Whether playback is going noticeably faster than chosen, to catch up with live. */
  get catchingUp(): boolean {
    return this.pace >= this.speed * NOTICEABLY_FASTER;
  }

  /** Everything received so far, in order; it only ever grows. */
  receive(events: readonly Event[]): void {
    const idle = this.shown === this.received;
    if (events.length > 0) this.firstArrival ??= this.now;
    // a Spectator who stepped past the first event, or jumped already, is no longer joining
    const joining = this.firstArrival !== null && this.now - this.firstArrival < JOINING_MS && this.shown <= 1;
    this.events = events;
    this.received = events.length;
    const latest = this.latestShown();
    if (idle && latest) {
      // after a quiet spell, the next event appears at once rather than in a burst of overdue ones
      this.shownAt = Math.max(this.shownAt, this.now - this.dwellAt(this.shown - 1));
    }
    if (joining && !this.detached && this.timeToCatchUp() > JOIN_AT_LIVE_MS) this.jumpToLive();
  }

  /** One animation frame's real time, counted up to a quarter second. */
  frame(realMs: number): void {
    this.tick(Math.min(realMs, MAX_FRAME_MS));
  }

  /** Let `realMs` of real time pass. */
  tick(realMs: number): void {
    if (this.held) return;
    this.now += realMs * this.pace;
    for (;;) {
      const latest = this.latestShown();
      if (latest && this.animating === latest.seq) {
        if (this.waitForAnimations && this.now - this.shownAt < ANIMATION_TIMEOUT_MS) return;
        this.animated(latest.seq, Math.min(this.now, this.shownAt + ANIMATION_TIMEOUT_MS));
      }
      const due = latest ? Math.max(this.shownAt + this.dwellAt(this.shown - 1), this.animatedAt) : this.shownAt;
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

  /** How long showing everything received would take at normal speed. Kept as a running sum,
   * since a live game's backlog arrives an event at a time: what was shown since is taken off
   * and what arrived is added, and only a step back counts it all again. */
  private timeToCatchUp(): number {
    const start = Math.max(this.shown - 1, 0);
    const end = Math.max(this.events.length - 1, start);
    let { from, to, ms } = this.backlog;
    if (start < from || start > to) [from, to, ms] = [start, start, 0];
    for (; from < start; from++) ms -= this.dwellAt(from);
    for (; to < end; to++) ms += this.dwellAt(to);
    this.backlog = { from, to, ms };
    return ms;
  }

  /** How long the event at `index` stays shown, given the one after it. */
  private dwellAt(index: number): number {
    const event = this.events[index];
    return event ? dwellOf(event, this.events[index + 1]) : 0;
  }
}
