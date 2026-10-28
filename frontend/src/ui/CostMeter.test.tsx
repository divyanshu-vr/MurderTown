/** Seam 3: the recorded game and a cost report go in; the cost meter a Spectator sees comes out. */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { payloadsOf, recordedGame } from "../../test/recordedGame";
import type { Cost, CostReport } from "../protocol";
import { GameConsole } from "./GameConsole";

const events = recordedGame();
const [started] = payloadsOf(events, "game_started");
const [first, second] = started?.residents ?? [];
if (!first || !second) throw new Error("The recorded game has no Residents");

function cost(calls: number, dollars: number, cacheRead = 0): Cost {
  const input = 100 * calls;
  return {
    calls,
    input_tokens: input,
    output_tokens: 20 * calls,
    cache_read_tokens: cacheRead,
    cache_write_tokens: 0,
    cost_usd: dollars,
    prompt_tokens: input + cacheRead,
    cache_hit_rate: input + cacheRead > 0 ? cacheRead / (input + cacheRead) : null,
  };
}

const report: CostReport = {
  total: cost(12, 0.0123, 400),
  residents: { [second.name]: cost(5, 0.005, 100), [first.name]: cost(6, 0.006, 300) },
  narrator: cost(1, 0.0013),
};

function meter() {
  return screen.getByRole("region", { name: "Cost" });
}

/** The meter, once the first cost report has arrived. */
function shownMeter() {
  return screen.findByRole("region", { name: "Cost" });
}

describe("the cost meter", () => {
  it("shows what the game's model calls cost in all", async () => {
    render(<GameConsole events={events} connection="ended" cost={() => Promise.resolve(report)} />);

    const totals = within(await shownMeter()).getByRole("list", {
      name: "Totals",
    });
    expect(totals).toHaveTextContent("Equivalent cost$0.0123");
    expect(totals).toHaveTextContent("Model calls12");
    expect(totals).toHaveTextContent("Prompt tokens1,600");
    expect(totals).toHaveTextContent("Tokens out240");
    expect(totals).toHaveTextContent("From cache25%");
  });

  it("lists each Resident in seat order, then the Narrator, so the rows add up to the total", async () => {
    render(<GameConsole events={events} connection="ended" cost={() => Promise.resolve(report)} />);

    const table = within(await shownMeter()).getByRole("table", { name: "Cost by caller" });
    const rows = within(table).getAllByRole("row").slice(1); // the first row is the header
    expect(rows.map((row) => within(row).getAllByRole("cell")[0]?.textContent)).toEqual([
      first.name,
      second.name,
      "Narrator",
    ]);
    expect(within(table).getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Caller",
      "Calls",
      "Prompt tokens",
      "Tokens out",
      "From cache",
      "Cost",
    ]);
    expect(rows[0]?.textContent).toBe(`${first.name}690012033%$0.0060`); // 300 of 900 prompt tokens from cache
  });

  it("hides each Resident's cost in mystery mode, where it would reveal who acts at Night", async () => {
    render(<GameConsole events={events} connection="ended" cost={() => Promise.resolve(report)} />);
    await shownMeter();

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    expect(within(meter()).queryByRole("table")).toBeNull();
    expect(within(meter()).getByRole("list", { name: "Totals" })).toHaveTextContent("$0.0123");
  });

  it("says when no model was called, as in a game of scripted Residents", async () => {
    const none: CostReport = { total: cost(0, 0), residents: {}, narrator: cost(0, 0) };
    render(<GameConsole events={events} connection="ended" cost={() => Promise.resolve(none)} />);

    expect(within(await shownMeter()).getByText("No model calls")).toBeInTheDocument();
  });

  it("is not shown without a cost report, as on a public-scope page", () => {
    render(<GameConsole events={events} connection="ended" />);

    expect(screen.queryByRole("region", { name: "Cost" })).toBeNull();
  });

  it("asks again only after new events arrive, one request at a time", async () => {
    let answer: (report: CostReport) => void = () => undefined;
    const source = vi.fn(() => new Promise<CostReport>((resolve) => (answer = resolve)));
    const shown = events.slice(0, 50);
    const { rerender } = render(<GameConsole events={shown} connection="live" cost={source} />);
    expect(source).toHaveBeenCalledTimes(1);

    rerender(<GameConsole events={events.slice(0, 60)} connection="live" cost={source} />);
    rerender(<GameConsole events={events.slice(0, 70)} connection="live" cost={source} />);
    expect(source).toHaveBeenCalledTimes(1); // the first request is still out

    await act(async () => answer(report));
    expect(source).toHaveBeenCalledTimes(2); // events arrived meanwhile, so it asks once more

    await act(async () => answer(report));
    rerender(<GameConsole events={events.slice(0, 70)} connection="live" cost={source} />);
    expect(source).toHaveBeenCalledTimes(2);
  });
});
