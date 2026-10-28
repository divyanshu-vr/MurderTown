/** Seam 3 (unit): playback on an injected clock decides when each event received is shown. */
import { describe, expect, it } from "vitest";

import { eventOf } from "../../test/events";
import type { Event } from "../protocol";
import { ANIMATION_TIMEOUT_MS, CATCH_UP_MS, MAX_FRAME_MS, nextSpeed, Playback } from "./playback";
import { dwellOf } from "./presentation";

const phase = () => eventOf({ type: "phase_started", day: 1, phase: "discussion" });
const died = () => eventOf({ type: "resident_died", resident: "Ava", cause: "banished", role: "civilian" });

/** A run of Phase starts, each shown for the same time. */
function phases(count: number): Event[] {
  return Array.from({ length: count }, phase);
}

const PHASE_DWELL = dwellOf(phase());

/** More Phase starts than a minute of watching: far enough behind to jump to live. */
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
    const playback = new Playback({ live: false, waitForAnimations: true });
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

  it("jumps to live when a live game is far behind, but plays a replay from the start", () => {
    const backlog = phases(PAST_A_MINUTE);
    const live = new Playback({ live: true });
    const replay = new Playback({ live: false });

    live.receive(backlog);
    replay.receive(backlog);

    expect(live.shown).toBe(PAST_A_MINUTE);
    expect(replay.shown).toBe(0);
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

    playback.skipToLive();
    expect([playback.shown, playback.behind, playback.held]).toEqual([PAST_A_MINUTE + 5, 0, false]);
  });

  it("follows live again once playing at the live edge, however it got there", () => {
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

      expect(playback.shown).toBe(PAST_A_MINUTE + 2);
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
});
