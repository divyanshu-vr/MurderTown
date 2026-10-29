/** Seam 3 (unit): playback on an injected clock decides when each event received is shown. */
import { describe, expect, it } from "vitest";

import { eventOf } from "../../test/events";
import type { Event } from "../protocol";
import { ANIMATION_TIMEOUT_MS, CATCH_UP_MS, JOINING_MS, MAX_CATCH_UP, MAX_FRAME_MS, nextSpeed, Playback } from "./playback";
import { dwellOf, HANDS_UP_MS } from "./presentation";

const phase = () => eventOf({ type: "phase_started", day: 1, phase: "discussion" });
const died = () => eventOf({ type: "resident_died", resident: "Ava", cause: "banished", role: "civilian" });
const bid = (resident: string) => eventOf({ type: "bid_placed", resident, urgency: 2, reason: "a point" });
const said = () =>
  eventOf({
    type: "statement_made",
    speaker: "Ava",
    text: "I saw nothing.",
    part: "open_floor",
    addressed: [],
    asked: null,
    answering: false,
    accused: [],
    defended: [],
    claimed_role: null,
    seconds_left: null,
  });

/** A run of Phase starts, each shown for the same time. */
function phases(count: number): Event[] {
  return Array.from({ length: count }, phase);
}

/** Whether counts of events shown never went up by more than one from one frame to the next. */
function oneAtATime(counts: readonly number[]): boolean {
  return counts.every((shown, i) => i === 0 || shown - (counts[i - 1] ?? 0) <= 1);
}

const PHASE_DWELL = dwellOf(phase());

/** More Phase starts than a minute of watching: far enough behind to catch up at full pace. */
const PAST_A_MINUTE = CATCH_UP_MS / PHASE_DWELL + 2;

describe("playing back a game", () => {
  it("shows each event once the one before has been shown for its time", () => {
    const playback = new Playback({ live: false });
    playback.receive(phases(3));

    playback.tick(0);
    expect(playback.shown).toBe(1);
    playback.tick(PHASE_DWELL - 1);
    expect(playback.shown).toBe(1);
    playback.tick(1);
    expect(playback.shown).toBe(2);
  });

  it("goes faster at a higher speed, shows everything due in one go, and stands still while held", () => {
    const playback = new Playback({ live: false });
    playback.receive(phases(10));

    playback.setSpeed(4);
    playback.tick(PHASE_DWELL / 4);
    expect(playback.shown).toBe(2);
    playback.tick(PHASE_DWELL / 2);
    expect(playback.shown).toBe(4);

    playback.hold();
    playback.tick(PHASE_DWELL * 5);
    expect(playback.shown).toBe(4);
  });

  it("speeds up and slows down a notch at a time, within the speeds on offer", () => {
    expect([nextSpeed(1, 1), nextSpeed(1, -1), nextSpeed(8, 1), nextSpeed(0.5, -1)]).toEqual([2, 0.5, 8, 0.5]);
  });

  it("moves one event at a time, forward and back, holding there", () => {
    const playback = new Playback({ live: false });
    playback.receive(phases(5));

    playback.next();
    playback.next();
    playback.previous();
    playback.tick(PHASE_DWELL * 5);

    expect(playback.shown).toBe(1);
    expect(playback.held).toBe(true);
  });

  it("seeks to any point of what has arrived", () => {
    const playback = new Playback({ live: false });
    playback.receive(phases(5));

    playback.seek(4);
    expect(playback.shown).toBe(4);
    playback.seek(99);
    expect(playback.shown).toBe(5);
  });

  it("holds a blocking moment for its animation, or a few seconds at most, then gives the next its full time", () => {
    const events = [died(), phase(), died(), phase(), phase()];
    const playback = new Playback({ live: false });
    playback.setWaitForAnimations(true);
    playback.receive(events);
    playback.tick(0);

    playback.tick(dwellOf(events[0] as Event));
    expect(playback.shown).toBe(1); // still animating
    playback.animated(events[0]?.seq ?? 0);
    playback.tick(0);
    expect(playback.shown).toBe(2);

    playback.tick(PHASE_DWELL); // the second death shows, and its animation never says it is done
    playback.tick(ANIMATION_TIMEOUT_MS - 1);
    expect(playback.shown).toBe(3);
    playback.tick(1);
    expect(playback.shown).toBe(4);
    playback.tick(PHASE_DWELL - 1);
    expect(playback.shown).toBe(4);
  });

  it("does not hold for an animation when nothing animates", () => {
    const events = [died(), phase()];
    const playback = new Playback({ live: false });
    playback.receive(events);

    playback.tick(dwellOf(events[0] as Event));

    expect(playback.shown).toBe(2);
  });

  it("holds for animations only while something animates them, and lets go when that stops", () => {
    const events = [died(), phase(), phase()];
    const playback = new Playback({ live: false });
    playback.receive(events);
    playback.setWaitForAnimations(true);
    playback.tick(0);

    playback.tick(dwellOf(events[0] as Event));
    expect(playback.shown).toBe(1);

    playback.setWaitForAnimations(false);
    playback.tick(0);
    expect(playback.shown).toBe(2);
    playback.tick(PHASE_DWELL - 1);
    expect(playback.shown).toBe(2); // the next event still gets its full time
  });

  it("counts a cut whenever the view jumps rather than plays on, so the town can snap to it", () => {
    const events = phases(5);
    const playback = new Playback({ live: true });
    playback.receive(events);
    playback.hold();
    const cuts = () => playback.cuts;

    playback.tick(PHASE_DWELL);
    playback.next();
    playback.play();
    playback.tick(PHASE_DWELL);
    expect(cuts()).toBe(0);

    playback.seek(1);
    playback.previous();
    playback.skipToLive();
    expect(cuts()).toBe(3);

    events.push(...phases(PAST_A_MINUTE)); // falling far behind plays faster rather than jumping
    playback.receive(events);
    expect(cuts()).toBe(3);
  });

  it("shows a Turn's Bids together, then the raised hands a moment before the Statement", () => {
    const playback = new Playback({ live: false });
    playback.receive([bid("Ava"), bid("Bo"), bid("Cy"), said()]);

    playback.tick(0);
    expect(playback.shown).toBe(3);
    playback.tick(HANDS_UP_MS - 1);
    expect(playback.shown).toBe(3);
    playback.tick(1);
    expect(playback.shown).toBe(4);
  });

  it("starts a live game joined far along at its live edge, but a replay at its start", () => {
    const backlog = phases(PAST_A_MINUTE);
    const live = new Playback({ live: true });
    const replay = new Playback({ live: false });

    live.receive(backlog);
    replay.receive(backlog);

    expect(live.shown).toBe(PAST_A_MINUTE);
    expect(replay.shown).toBe(0);
  });

  it("starts at the live edge of a game joined far along whose backlog arrives an event at a time", () => {
    const backlog = phases(PAST_A_MINUTE);
    const live = new Playback({ live: true });

    for (let count = 1; count <= backlog.length; count++) {
      live.receive(backlog.slice(0, count));
      live.tick(1);
    }

    expect(live.shown).toBe(PAST_A_MINUTE);
    expect(live.cuts).toBe(1);
  });

  it("takes a Spectator who skipped to live before anything arrived to the live edge once it does", () => {
    const live = new Playback({ live: true });
    live.skipToLive();

    live.receive(phases(PAST_A_MINUTE));

    expect(live.shown).toBe(PAST_A_MINUTE);
  });

  it("plays faster to catch up when a live game falls behind, up to a limit, and shows everything", () => {
    const events = phases(1);
    const playback = new Playback({ live: true });
    playback.receive(events);
    playback.tick(JOINING_MS); // a game watched for a while, not one just joined

    events.push(...phases(PAST_A_MINUTE));
    playback.receive(events);
    expect(playback.shown).toBe(1);
    expect(playback.pace).toBe(MAX_CATCH_UP);

    const seen = [playback.shown];
    while (playback.behind > 0) {
      playback.tick(MAX_FRAME_MS);
      seen.push(playback.shown);
    }
    expect(oneAtATime(seen)).toBe(true);
    expect(playback.pace).toBe(1);
  });

  it("leaves the Spectator's own pace alone until they skip to live", () => {
    const events = phases(5);
    const playback = new Playback({ live: true });
    playback.receive(events);
    playback.hold();

    events.push(...phases(PAST_A_MINUTE));
    playback.receive(events);
    expect(playback.shown).toBe(0);
    expect(playback.behind).toBe(PAST_A_MINUTE + 5);
    expect(playback.pace).toBe(playback.speed);

    playback.skipToLive();
    expect([playback.shown, playback.behind, playback.held]).toEqual([PAST_A_MINUTE + 5, 0, false]);
  });

  it("catches up with live again once playing at the live edge, however it got there", () => {
    const reached = [
      (playback: Playback) => {
        playback.setSpeed(2);
        playback.tick(PHASE_DWELL);
      },
      (playback: Playback) => playback.seek(2),
      (playback: Playback) => {
        playback.next();
        playback.next();
        playback.play();
      },
    ];
    for (const reach of reached) {
      const events = phases(2);
      const playback = new Playback({ live: true });
      playback.receive(events);
      reach(playback);
      expect(playback.shown).toBe(2);

      events.push(...phases(PAST_A_MINUTE));
      playback.receive(events);

      expect(playback.pace).toBeGreaterThan(playback.speed);
    }
  });

  it("does not leap ahead after a hidden tab: a frame counts a quarter second at most", () => {
    const playback = new Playback({ live: false });
    playback.receive(phases(10));
    playback.tick(0);

    playback.frame(60_000);
    playback.frame(PHASE_DWELL - MAX_FRAME_MS - 1);

    expect(playback.shown).toBe(1);
  });

  it("shows an event that arrives after a quiet spell at once, then keeps its usual pace", () => {
    const events = phases(1);
    const playback = new Playback({ live: true });
    playback.receive(events);
    playback.tick(0);
    for (let i = 0; i < 40; i++) playback.tick(250); // ten quiet seconds

    events.push(...phases(2));
    playback.receive(events);
    playback.tick(0);
    expect(playback.shown).toBe(2);
    playback.tick(PHASE_DWELL - 1);
    expect(playback.shown).toBe(2);
  });

  it("tells how long ago each event it played on to was shown, quiet spells and all, until the view jumps", () => {
    const events = phases(2);
    const playback = new Playback({ live: true });
    const sinceShown = () => events.map(({ seq }) => playback.sinceShown(seq));
    playback.receive(events);
    playback.tick(0);
    playback.tick(PHASE_DWELL);
    expect(sinceShown()).toEqual([PHASE_DWELL, 0]);

    for (let i = 0; i < 40; i++) playback.tick(250); // ten quiet seconds
    events.push(...phases(1));
    playback.receive(events);
    playback.tick(0);
    expect(sinceShown()).toEqual([PHASE_DWELL + 10_000, 10_000, 0]);

    playback.hold();
    playback.tick(5000);
    expect(sinceShown()).toEqual([PHASE_DWELL + 10_000, 10_000, 0]);

    playback.seek(2);
    expect(sinceShown()).toEqual([null, 0, null]);
  });
});
