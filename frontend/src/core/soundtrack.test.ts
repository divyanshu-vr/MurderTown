/** Seam 3 (unit): what the recorded game sounds like as playback shows it. */
import { describe, expect, it } from "vitest";

import { eventOf } from "../../test/events";
import { present } from "../../test/present";
import { countOf, eventsOf, recordedGame } from "../../test/recordedGame";
import { snapshotsOf, viewAt } from "./snapshots";
import { type Frame, LETTERS_PER_BLIP, type Sounds, Soundtrack, stingOf, themeOf, voiceOf } from "./soundtrack";

const events = recordedGame();
const snapshots = snapshotsOf(events);

/** Playback showing the first `count` events, the latest of them for `ms`, playing on. */
function frame(count: number, changes: Partial<Frame> = {}, ms = 0): Frame {
  const shown = events.slice(0, count);
  const latest = shown.at(-1)?.seq;
  return {
    events: shown,
    view: viewAt(events, snapshots, count),
    cuts: 0,
    held: false,
    mystery: false,
    sinceShown: (seq) => (seq === latest ? ms : null),
    ...changes,
  };
}

/** The stings heard playing on from showing `from` events to showing `to`. */
function stingsPlayingOn(soundtrack: Soundtrack, from: number, to: number, changes: Partial<Frame> = {}): Sounds["sting"][] {
  const heard: Sounds["sting"][] = [];
  for (let count = from; count <= to; count++) heard.push(soundtrack.next(frame(count, changes)).sting);
  return heard.filter(Boolean);
}

const speaking = present(eventsOf(events, "statement_made")[0], "a Statement");
const speaker = present(
  eventsOf(events, "game_started")[0]?.payload.residents.find(({ name }) => name === speaking.payload.speaker),
  "the speaker",
);

describe("the sound of the game", () => {
  it("plays the day theme by day and the night theme at Night, and no music before the game or after it", () => {
    expect(themeOf("dawn")).toBe("day");
    expect(themeOf("vote")).toBe("day");
    expect(themeOf("dusk")).toBe("day");
    expect(themeOf("night")).toBe("night");
    expect(themeOf("setup")).toBeNull();
    expect(themeOf("ended")).toBeNull();
  });

  it("has a sting for each Phase, Ballot, Vote result, Banishment, shot and murder found, and for each side's win", () => {
    const deaths = eventsOf(events, "resident_died");
    const murder = present(deaths.find(({ payload }) => payload.cause === "murdered"), "a murder");
    const banishment = present(deaths.find(({ payload }) => payload.cause === "banished"), "a Banishment");
    const won = (winner: "town" | "murderers") => eventOf({ type: "game_ended", winner, reason: "" });

    expect(stingOf(murder)).toBe("murder");
    expect(stingOf(banishment)).toBe("banishment");
    expect(eventsOf(events, "sheriff_fired").map(stingOf)).toContain("shot");
    expect(eventsOf(events, "ballot_cast").map(stingOf)).toContain("ballot");
    expect(eventsOf(events, "vote_resolved").map(stingOf)).toContain("vote-result");
    expect(eventsOf(events, "phase_started").map(stingOf)).toContain("phase");
    expect([stingOf(won("town")), stingOf(won("murderers"))]).toEqual(["town-wins", "murderers-win"]);
    expect(stingOf(speaking)).toBeNull();
  });

  it("plays each sting once, at its moment, as playback plays on", () => {
    const soundtrack = new Soundtrack();
    const heard = stingsPlayingOn(soundtrack, 1, events.length);

    expect(heard).toEqual(events.map(stingOf).filter(Boolean));
    expect(soundtrack.next(frame(events.length)).sting).toBeNull();
  });

  it("plays nothing for the events a jump passes over, nor while held", () => {
    const shot = present(eventsOf(events, "sheriff_fired")[0], "the Sheriff's shot");
    const result = present(eventsOf(events, "vote_resolved").find(({ seq }) => seq > shot.seq), "the Vote after it");
    const showdown = countOf(events, shot) - 1; // up to the Showdown's start
    const ballots = eventsOf(events, "ballot_cast").filter(({ seq }) => seq > shot.seq && seq < result.seq);
    const soundtrack = new Soundtrack();
    soundtrack.next(frame(10));

    expect(soundtrack.next(frame(showdown - 1, { cuts: 1 }))).toMatchObject({ sting: null, blip: null });
    expect(stingsPlayingOn(soundtrack, showdown, countOf(events, result), { cuts: 1 })).toEqual([
      "phase",
      "shot",
      "phase",
      ...ballots.map(() => "ballot"),
      "vote-result",
    ]);
    const later = countOf(events, result) + 20;
    expect(soundtrack.next(frame(later, { cuts: 1, held: true }))).toMatchObject({ sting: null, blip: null });
    expect(soundtrack.next(frame(later, { cuts: 1 })).sting).toBeNull();
  });

  it("plays only the most telling sting when fast playback shows several events at once", () => {
    const result = present(eventsOf(events, "vote_resolved")[0], "a Vote result");
    const soundtrack = new Soundtrack();
    soundtrack.next(frame(countOf(events, result) - 4));

    expect(soundtrack.next(frame(countOf(events, result))).sting).toBe("vote-result"); // the last Ballots, then the result
  });

  it("voices words in their speaker's pitch as they type out, a blip every few letters, then falls quiet", () => {
    const count = countOf(events, speaking);
    const soundtrack = new Soundtrack();
    soundtrack.next(frame(count, {}, 0));
    const blips: (number | null)[] = [];
    for (let ms = 50; ms <= 20_000; ms += 50) blips.push(soundtrack.next(frame(count, {}, ms)).blip);
    const voiced = blips.filter((blip) => blip !== null);

    expect(new Set(voiced)).toEqual(new Set([voiceOf(speaker.seat)]));
    expect(voiced).toHaveLength(Math.ceil(speaking.payload.text.length / LETTERS_PER_BLIP));
    expect(blips.slice(-10).every((blip) => blip === null)).toBe(true);
  });

  it("does not voice words shown whole, as after a jump or a step while held", () => {
    const count = countOf(events, speaking);
    const blipsPlayingOn = (soundtrack: Soundtrack, changes: Partial<Frame>) =>
      [50, 500, 5000].map((ms) => soundtrack.next(frame(count, changes, ms)).blip).filter((blip) => blip !== null);
    const jumped = new Soundtrack();
    jumped.next(frame(10));
    jumped.next(frame(count, { cuts: 1 }));
    const stepped = new Soundtrack();
    stepped.next(frame(count - 1, { held: true }));
    stepped.next(frame(count, { held: true }));

    expect(blipsPlayingOn(jumped, { cuts: 1 })).toEqual([]);
    expect(blipsPlayingOn(stepped, {})).toEqual([]);
  });

  it("gives every seat its own voice, and the Narrator a voice lower than them all", () => {
    const voices = Array.from({ length: 15 }, (_, seat) => voiceOf(seat));

    expect(new Set(voices).size).toBe(15);
    expect(voiceOf(null)).toBeLessThan(Math.min(...voices));
  });
});
