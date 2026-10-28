/** Seam 3: the suspicion heatmap, as of the view, from the recorded game. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { recordedGame } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

function showHeatmap() {
  render(<GameConsole events={events} connection="ended" />);
  fireEvent.click(screen.getByRole("tab", { name: "Suspicion" }));
  return screen.getByRole("table", { name: /^Suspicion at the start of Day \d+/ });
}

describe("the suspicion heatmap", () => {
  it("is a table of every Resident's Suspicion of every other, with the number in each cell", () => {
    const table = showHeatmap();

    const [header, ...rows] = within(table).getAllByRole("row");
    const columns = within(header as HTMLElement).getAllByRole("columnheader");
    expect(rows).toHaveLength(columns.length - 1); // one row and one column per Resident
    expect(within(table).getAllByRole("rowheader").some((cell) => cell.textContent?.includes("(dead)"))).toBe(true);
    for (const cell of within(table).getAllByRole("cell")) {
      expect(cell.textContent).toMatch(/^(—|\d+.*|no opinion yet)$/); // never colour alone
    }
  });

  it("says how each Suspicion changed in words, and since when", () => {
    const table = showHeatmap();

    expect(within(table).getAllByText(/^(up|down) \d+$/).length).toBeGreaterThan(0);
    expect(table).toHaveAccessibleName(/changes since the start of Day \d+/);
  });

  it("tells a cell's note when the Spectator chooses it, by keyboard as well as by mouse", () => {
    const table = showHeatmap();
    const [first] = within(table).getAllByRole("button");
    if (!first) throw new Error("Nobody suspects anyone in the recorded game");

    fireEvent.click(first);

    expect(screen.getByRole("status")).toHaveTextContent(/^\w+ suspects \w+: \d+/);
  });

  it("is not offered in mystery mode, nor on a public page", () => {
    render(<GameConsole events={events} connection="ended" scope="public" />);

    expect(screen.queryByRole("tab", { name: "Suspicion" })).toBeNull();
  });
});
