/** Seam 3: the console shows only what playback has reached, and the Spectator steers playback. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Speed } from "../core/playback";
import { playbackAt } from "../../test/playback";
import { recordedGame } from "../../test/recordedGame";
import { describeEvent, inFeed } from "./describeEvent";
import { GameConsole } from "./GameConsole";
import type { PlaybackView } from "./usePlayback";

const events = recordedGame();

/** A playback that shows `shown` events and notes what the Spectator asks of it. */
function playback(shown: number, live = true): PlaybackView & { asked: string[] } {
  const asked: string[] = [];
  const note = (what: string) => () => {
    asked.push(what);
  };
  return {
    asked,
    ...playbackAt(shown, events.length, {
      held: false,
      live,
      play: note("play"),
      hold: note("hold"),
      next: note("next"),
      previous: note("previous"),
      seek: (count: number) => asked.push(`seek ${count}`),
      setSpeed: (speed: Speed) => asked.push(`speed ${speed}`),
      skipToLive: note("skip to live"),
    }),
  };
}

function controls() {
  return screen.getByRole("group", { name: "Playback" });
}

describe("watching at one's own pace", () => {
  it("shows only the events playback has reached, and how far behind it is", () => {
    render(<GameConsole events={events} connection="live" playback={playback(12)} />);

    const lines = within(screen.getByRole("log", { name: "Town feed" })).getAllByRole("listitem");
    expect(lines.map((line) => line.textContent)).toEqual(events.slice(0, 12).filter(inFeed).map(describeEvent));
    expect(controls()).toHaveTextContent(`${events.length - 12} events behind`);
  });

  it("holds, moves an event at a time, changes speed, seeks and skips to live from its controls", () => {
    const steered = playback(12);
    render(<GameConsole events={events} connection="live" playback={steered} />);

    for (const name of ["Hold", "Previous event", "Next event", "Skip to live"]) {
      fireEvent.click(within(controls()).getByRole("button", { name }));
    }
    fireEvent.change(within(controls()).getByRole("combobox", { name: "Speed" }), { target: { value: "4" } });
    fireEvent.change(within(controls()).getByRole("slider", { name: "Timeline" }), { target: { value: "30" } });

    expect(steered.asked).toEqual(["hold", "previous", "next", "skip to live", "speed 4", "seek 30"]);
  });

  it("offers to skip to the end of a replay, and its link only once the view reaches the end", () => {
    const replay = (shown: number) => (
      <GameConsole events={events} connection="ended" playback={playback(shown, false)} replayUrl="http://web/games/a1/replay" />
    );
    const { rerender } = render(replay(12));
    expect(within(controls()).getByRole("button", { name: "Skip to the end" })).toBeInTheDocument();
    expect(within(controls()).queryByRole("link", { name: "Replay link" })).toBeNull();
    expect(screen.getByRole("banner")).toHaveTextContent("Replay"); // not "Finished": that would give the end away

    rerender(replay(events.length));

    expect(within(controls()).getByRole("link", { name: "Replay link" })).toHaveAttribute(
      "href",
      "http://web/games/a1/replay",
    );
    expect(screen.getByRole("banner")).toHaveTextContent("Finished");
  });

  it("answers the keyboard: Space, the arrows, L, minus and equals, and M for mystery mode", () => {
    const steered = playback(12);
    render(<GameConsole events={events} connection="live" playback={steered} />);

    for (const key of [" ", "ArrowLeft", "ArrowRight", "l", "-", "=", "m"]) {
      fireEvent.keyDown(document.body, { key });
    }

    expect(steered.asked).toEqual(["hold", "previous", "next", "skip to live", "speed 0.5", "speed 2"]);
    expect(screen.getByRole("button", { name: "Mystery mode" })).toHaveAttribute("aria-pressed", "true");
  });

  it("leaves to a focused control only the keys it uses itself", () => {
    const steered = playback(12);
    render(<GameConsole events={events} connection="live" playback={steered} />);
    const button = within(controls()).getByRole("button", { name: "Hold" });
    const slider = within(controls()).getByRole("slider", { name: "Timeline" });

    fireEvent.keyDown(button, { key: " " }); // the button's own press
    fireEvent.keyDown(slider, { key: "ArrowLeft" }); // the slider's own move
    fireEvent.keyDown(button, { key: "ArrowRight" });
    fireEvent.keyDown(slider, { key: "l" });

    expect(steered.asked).toEqual(["next", "skip to live"]);
  });
});
