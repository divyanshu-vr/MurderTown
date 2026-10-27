/** Seam 3: a recorded event log goes in; what a Spectator sees in the console comes out. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { payloadsOf, recordedGame } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

function upTo(predicate: (index: number) => boolean) {
  return events.filter((_, index) => predicate(index));
}

describe("the game console", () => {
  it("shows the Day and Phase of the latest event in the phase bar", () => {
    const firstDayTwoVote = events.findIndex(
      (e) => e.payload.type === "phase_started" && e.payload.day === 2 && e.payload.phase === "vote",
    );
    render(<GameConsole events={upTo((index) => index <= firstDayTwoVote)} connection="live" />);

    const phaseBar = screen.getByRole("banner");
    expect(phaseBar).toHaveTextContent("Day 2");
    expect(phaseBar).toHaveTextContent("Vote");
  });

  it("lists every Statement in the feed, in the order they were made", () => {
    render(<GameConsole events={events} connection="ended" />);

    const statements = payloadsOf(events, "statement_made");
    const feed = screen.getByRole("log", { name: "Town feed" });
    const shown = within(feed)
      .getAllByRole("listitem")
      .filter((item) => item.dataset.kind === "statement_made")
      .map((item) => item.textContent);

    expect(shown).toHaveLength(statements.length);
    expect(shown[0]).toContain(statements[0]?.text);
    expect(shown.at(-1)).toContain(statements.at(-1)?.text);
  });

  it("shows every banished Resident as dead, with their revealed role", () => {
    render(<GameConsole events={events} connection="ended" />);

    const roster = screen.getByRole("list", { name: "Residents" });
    const deaths = payloadsOf(events, "resident_died");
    expect(deaths.length).toBeGreaterThan(0);
    for (const death of deaths) {
      const row = within(roster).getByRole("listitem", { name: death.resident });
      expect(row).toHaveTextContent("Banished");
      expect(row).toHaveTextContent(new RegExp(death.role, "i"));
    }
  });

  it("announces the winner and the reason once the game is over", () => {
    render(<GameConsole events={events} connection="ended" />);

    const [ending] = payloadsOf(events, "game_ended");
    const phaseBar = screen.getByRole("banner");
    expect(phaseBar).toHaveTextContent(ending?.winner === "town" ? "The Town wins" : "The Murderers win");
    expect(phaseBar).toHaveTextContent(ending?.reason ?? "");
  });
});
