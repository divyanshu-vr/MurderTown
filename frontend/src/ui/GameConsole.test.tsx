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
  it("can start in mystery mode, which the Spectator can still leave", () => {
    render(<GameConsole events={events} connection="live" startsInMystery />);

    const mystery = screen.getByRole("button", { name: "Mystery mode" });
    expect(mystery).toHaveAttribute("aria-pressed", "true");
    expect(within(feed()).queryAllByRole("listitem").filter(isKind("resident_investigated"))).toHaveLength(0);

    fireEvent.click(mystery);

    expect(feedItems("resident_investigated").length).toBeGreaterThan(0);
  });

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

  // renders the whole recorded game twice, which jsdom takes a few seconds to do
  it("shows Dusk and the Night in full, and in mystery mode only what the whole town saw", { timeout: 20_000 }, () => {
    render(<GameConsole events={events} connection="ended" />);
    const secret: Kind[] = [
      "den_message_posted",
      "kill_vote_cast",
      "victim_chosen",
      "resident_protected",
      "resident_investigated",
      "dusk_intent_chosen",
      "conversation_message_posted",
    ];
    const told: Kind[] = ["attack_thwarted", "recap_narrated", "conversation_started"];
    for (const kind of [...secret, ...told]) expect(feedItems(kind).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    for (const kind of secret) expect(within(feed()).queryAllByRole("listitem").filter(isKind(kind))).toHaveLength(0);
    for (const kind of told) expect(feedItems(kind).length).toBeGreaterThan(0);
    const words = payloadsOf(events, "conversation_message_posted").map((message) => message.text);
    expect(feed().textContent).not.toContain(`"${words[0]}"`);
    const murdered = payloadsOf(events, "resident_died").filter((death) => death.cause === "murdered");
    expect(feedItems("resident_died").map((item) => item.textContent)).toEqual(
      expect.arrayContaining(murdered.map((death) => expect.stringContaining(`${death.resident} is found murdered`))),
    );
  });
});

describe("an aborted game", () => {
  const firstKillVote = events.findIndex((event) => event.payload.type === "kill_vote_cast");
  const before = events.slice(0, firstKillVote);
  const lastKept = before.at(-1);
  const vote = events[firstKillVote];
  if (!lastKept || vote?.payload.type !== "kill_vote_cast") throw new Error("The recorded game has no kill vote");
  const murderer = vote.payload.murderer;
  const unanswered: Event = {
    seq: lastKept.seq + 1,
    day: lastKept.day,
    phase: lastKept.phase,
    visibility: { scope: "spectators", residents: [] },
    decision_id: "d999",
    payload: { type: "decision_unanswered", resident: murderer, kind: "kill_vote", reason: "no answer within 90 seconds" },
  };
  const abort: Event = {
    ...unanswered,
    seq: unanswered.seq + 1,
    visibility: { scope: "everyone", residents: [] },
    decision_id: null,
    payload: { type: "game_aborted", reason: "no answer within 90 seconds" },
  };
  const aborted = [...before, unanswered, abort];

  it("says the game was aborted and why, as an alert", () => {
    render(<GameConsole events={aborted} connection="ended" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Game aborted: no answer within 90 seconds");
  });

  it("tells in the feed whose decision got no answer", () => {
    render(<GameConsole events={aborted} connection="ended" />);

    const [line] = feedItems("decision_unanswered");
    expect(line).toHaveTextContent(`${murderer}'s kill vote got no answer: no answer within 90 seconds`);
  });

  it("names no one in mystery mode, where it could reveal a Night role", () => {
    render(<GameConsole events={aborted} connection="ended" />);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Game aborted: no answer within 90 seconds");
    expect(alert).not.toHaveTextContent(murderer);
    expect(alert.textContent?.toLowerCase()).not.toContain("kill");
    expect(within(feed()).queryAllByRole("listitem").filter(isKind("decision_unanswered"))).toHaveLength(0);
    const [line] = feedItems("game_aborted");
    expect(line).toHaveTextContent("The game is aborted: no answer within 90 seconds");
    expect(line).not.toHaveTextContent(murderer);
  });

  it("lists the decision that got no answer in that Resident's mind, ready to explain", () => {
    render(<GameConsole events={aborted} connection="ended" explain={() => Promise.reject(new Error("unused"))} />);

    const roster = screen.getByRole("list", { name: "Residents" });
    fireEvent.click(within(roster).getByRole("button", { name: murderer }));
    const mind = screen.getByRole("complementary", { name: `Mind of ${murderer}` });
    const decisions = within(mind).getByRole("list", { name: "Decisions" });
    const item = within(decisions).getByRole("listitem", { name: `Decision at event ${unanswered.seq}` });
    expect(within(item).getByRole("button", { name: "why?" })).toBeInTheDocument();
  });
});

describe("a paused game", () => {
  it("says so in the phase bar, to everyone watching", () => {
    render(<GameConsole events={events} connection="live" scope="public" paused />);

    expect(screen.getByRole("banner")).toHaveTextContent("Paused");
  });
});

describe("an Open floor that ran out of time", () => {
  it("says so in the feed, before the next Phase starts", () => {
    const lastOpenFloor = events.findLastIndex(
      (event) => event.payload.type === "statement_made" && event.payload.part === "open_floor",
    );
    const said = events[lastOpenFloor];
    if (!said) throw new Error("The recorded game has no Open floor");
    const timedOut: Event = { ...said, seq: said.seq + 1, decision_id: null, payload: { type: "open_floor_timed_out" } };
    render(<GameConsole events={[...events.slice(0, lastOpenFloor + 1), timedOut]} connection="live" />);

    const [line] = feedItems("open_floor_timed_out");
    expect(line).toHaveTextContent("Time is up on the Open floor.");
  });
});
