/** Seam 3: the countdown to the Vote in the phase bar, on the recorded game. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { firstOnTheFloor, lastOpening, shownAgo, timedGame, upTo } from "../../test/openFloor";
import { playbackAt } from "../../test/playback";
import { GameConsole } from "./GameConsole";
import { VoteCountdown } from "./VoteCountdown";

const events = timedGame(180);
const upToIt = upTo(events, firstOnTheFloor);

const timer = () => screen.getByRole("timer", { name: "Until the Vote" });

afterEach(() => {
  vi.useRealTimers();
});

describe("the countdown to the Vote", () => {
  it("shows the time and the Statements left in the phase bar during the Open floor", () => {
    const playback = playbackAt(upToIt.length, events.length, { sinceShown: shownAgo(41_000, lastOpening) });
    render(<GameConsole events={events} connection="ended" playback={playback} />);

    expect(screen.getByRole("banner")).toHaveTextContent("Vote in 2:19 · 7 Statements left");
  });

  it("counts down while playback plays", () => {
    vi.useFakeTimers();
    let ago = 41_000;
    render(<VoteCountdown events={upToIt} playback={{ sinceShown: (seq) => (seq === lastOpening.seq ? ago : null), held: false }} />);

    ago += 1000;
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(timer()).toHaveTextContent("Vote in 2:18 · 7 Statements left");
  });

  it("says the Vote is due any moment once the time is up", () => {
    render(<VoteCountdown events={upToIt} playback={{ sinceShown: shownAgo(10 * 60_000, lastOpening), held: true }} />);

    expect(timer()).toHaveTextContent("Vote any moment · 7 Statements left");
  });

  it("is not there outside the Open floor", () => {
    render(<VoteCountdown events={events.filter(({ seq }) => seq < lastOpening.seq)} />);

    expect(screen.queryByRole("timer")).toBeNull();
  });
});
