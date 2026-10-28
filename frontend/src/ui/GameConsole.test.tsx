/** Seam 3: a recorded event log goes in; what a Spectator sees in the console comes out. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Event } from "../protocol";
import { payloadsOf, recordedGame } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

function upTo(predicate: (index: number) => boolean) {
  return events.filter((_, index) => predicate(index));
}

function feed() {
  return screen.getByRole("log", { name: "Town feed" });
}

type Kind = Event["payload"]["type"];

function isKind(kind: Kind) {
  return (item: HTMLElement) => item.dataset.kind === kind;
}

/** The feed's lines for one kind of event. */
function feedItems(kind: Kind) {
  return within(feed()).getAllByRole("listitem").filter(isKind(kind));
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
    expect(new Set(deaths.map((death) => death.cause))).toEqual(new Set(["banished", "shot", "backfire", "murdered"]));
    const marks = { banished: "Banished", shot: "Shot", backfire: "Backfire", murdered: "Murdered" };
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

  it("shows the Night in full, and in mystery mode only what Dawn tells the whole town", () => {
    render(<GameConsole events={events} connection="ended" />);
    const secret: Kind[] = [
      "den_message_posted",
      "kill_vote_cast",
      "victim_chosen",
      "resident_protected",
      "resident_investigated",
    ];
    const told: Kind[] = ["attack_thwarted", "recap_narrated"];
    for (const kind of [...secret, ...told]) expect(feedItems(kind).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    for (const kind of secret) expect(within(feed()).queryAllByRole("listitem").filter(isKind(kind))).toHaveLength(0);
    for (const kind of told) expect(feedItems(kind).length).toBeGreaterThan(0);
    const murdered = payloadsOf(events, "resident_died").filter((death) => death.cause === "murdered");
    expect(feedItems("resident_died").map((item) => item.textContent)).toEqual(
      expect.arrayContaining(murdered.map((death) => expect.stringContaining(`${death.resident} is found murdered`))),
    );
  });
});
