/**
 * Seam 3: the console beside the Town view, from the recorded game. jsdom has no WebGL, so a
 * stand-in takes the place of the town's own chunk and shows what it was given.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { playbackAt } from "../../test/playback";
import { countWhen, recordedGame } from "../../test/recordedGame";
import type { TownCanvasProps } from "../game/TownCanvas";
import { GameConsole } from "./GameConsole";

vi.mock("../game/TownCanvas", () => ({
  default: ({ view }: TownCanvasProps) => <p>The town at {view.phase}</p>,
}));

// jsdom has no media queries; this Spectator does not ask for reduced motion
vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query }));

const events = recordedGame();
const DAY_2_VOTE = countWhen(events, "vote", 2);

function watchTheTown() {
  render(
    <GameConsole events={events} connection="live" playback={playbackAt(DAY_2_VOTE, events.length)} townView />,
  );
}

const tab = (name: string) => screen.getByRole("tab", { name });

describe("the console beside the Town view", () => {
  it("draws the town as far as playback has reached", async () => {
    watchTheTown();

    expect(await within(screen.getByRole("region", { name: "Town view" })).findByText("The town at vote")).toBeVisible();
  });

  it("makes every panel a tab, the feed first", () => {
    watchTheTown();

    expect(screen.getAllByRole("tab").map((each) => each.textContent)).toEqual(["Feed", "Residents", "Suspicion"]);
    expect(tab("Feed")).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("list", { name: "Residents" })).toBeNull();
  });

  it("opens a Resident's mind in a tab of its own, and goes back to the Residents when it closes", () => {
    watchTheTown();

    fireEvent.click(tab("Residents"));
    const first = within(screen.getByRole("list", { name: "Residents" })).getAllByRole("button")[0];
    fireEvent.click(first as HTMLElement);

    expect(tab("Mind")).toHaveAttribute("aria-selected", "true");
    const mind = screen.getByRole("complementary", { name: `Mind of ${first?.textContent ?? ""}` });
    fireEvent.click(within(mind).getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("tab", { name: "Mind" })).toBeNull();
    expect(tab("Residents")).toHaveAttribute("aria-selected", "true");
  });
});
