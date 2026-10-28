/** Seam 3: a recorded event log goes in; what a Spectator sees in the console comes out. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Event } from "../protocol";
import { payloadsOf, recordedGame } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

function upTo(predicate: (index: number) => boolean) {
  return events.filter((_, index) => predicate(index));
}

/** The feed's lines for one kind of event. */
function feedItems(kind: Event["payload"]["type"]) {
  const feed = screen.getByRole("log", { name: "Town feed" });
  return within(feed)
    .getAllByRole("listitem")
    .filter((item) => item.dataset.kind === kind);
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
    const shown = feedItems("statement_made").map((item) => item.textContent);

    expect(shown).toHaveLength(statements.length);
    expect(shown[0]).toContain(statements[0]?.text);
    expect(shown.at(-1)).toContain(statements.at(-1)?.text);
  });

  it("shows every dead Resident with how they died and their revealed role", () => {
    render(<GameConsole events={events} connection="ended" />);

    const roster = screen.getByRole("list", { name: "Residents" });
    const deaths = payloadsOf(events, "resident_died");
    expect(new Set(deaths.map((death) => death.cause))).toEqual(new Set(["banished", "shot", "backfire"]));
    const marks = { banished: "Banished", shot: "Shot", backfire: "Backfire" };
    for (const death of deaths) {
      const row = within(roster).getByRole("listitem", { name: death.resident });
      expect(row).toHaveTextContent(marks[death.cause]);
      expect(row).toHaveTextContent(new RegExp(death.role, "i"));
    }
  });

  it("counts the Open floor's Statements against its cap while it is under way", () => {
    const isOpenFloor = (e: Event) => e.payload.type === "statement_made" && e.payload.part === "open_floor";
    const firstOnOpenFloor = events.findIndex(isOpenFloor);
    const view = render(<GameConsole events={upTo((i) => i <= firstOnOpenFloor)} connection="live" />);

    expect(screen.getByRole("banner")).toHaveTextContent("Open floor: 1 of 8 Statements");

    const nextPhase = events.findIndex((e, i) => i > firstOnOpenFloor && e.payload.type === "phase_started");
    view.rerender(<GameConsole events={upTo((i) => i <= nextPhase)} connection="live" />);
    expect(screen.getByRole("banner")).not.toHaveTextContent("Open floor");
  });

  it("shows the bids of Residents who want to speak, and leaves out those who only listen", () => {
    render(<GameConsole events={events} connection="ended" />);

    const eager = payloadsOf(events, "bid_placed").filter((bid) => bid.urgency > 0);
    expect(eager.length).toBeGreaterThan(0);
    expect(feedItems("bid_placed")).toHaveLength(eager.length);
  });

  it("shows the Sheriff's shot and the last words of the banished in the feed", () => {
    render(<GameConsole events={events} connection="ended" />);

    const shots = payloadsOf(events, "sheriff_fired");
    const lastWords = payloadsOf(events, "last_words_spoken");
    expect(shots).toHaveLength(1);
    expect(feedItems("sheriff_fired")[0]).toHaveTextContent(`fires at ${shots[0]?.target}`);
    expect(feedItems("last_words_spoken").map((item) => item.textContent)).toEqual(
      lastWords.map((words) => `${words.resident}'s last words: "${words.text}"`),
    );
  });

  it("shows each Resident's occupation in the roster", () => {
    render(<GameConsole events={events} connection="ended" />);

    const [started] = payloadsOf(events, "game_started");
    const roster = screen.getByRole("list", { name: "Residents" });
    for (const resident of started?.residents ?? []) {
      expect(within(roster).getByRole("listitem", { name: resident.name })).toHaveTextContent(
        resident.occupation,
      );
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
