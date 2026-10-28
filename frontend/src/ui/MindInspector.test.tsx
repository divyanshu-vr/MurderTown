/** Seam 3: the recorded game goes in; what the Mind inspector shows at a given moment comes out. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { eventsOf, payloadsOf, recordedGame } from "../../test/recordedGame";
import type { Event, Explanation, ModelCall } from "../protocol";
import { GameConsole } from "./GameConsole";

const events = recordedGame();
const notes = eventsOf(events, "reflection_written");

function upTo(seq: number) {
  return events.filter((event) => event.seq <= seq);
}

function found<T>(value: T | undefined, what: string): T {
  if (value === undefined) throw new Error(`The recorded game has no ${what}`);
  return value;
}

function inspect(name: string) {
  const roster = screen.getByRole("list", { name: "Residents" });
  fireEvent.click(within(roster).getByRole("button", { name }));
  return screen.getByRole("complementary", { name: `Mind of ${name}` });
}

function section(mind: HTMLElement, title: string) {
  const heading = within(mind).getByRole("heading", { name: title });
  return found(heading.parentElement ?? undefined, `${title} section`);
}

describe("the Mind inspector", () => {
  it("opens from the roster and shows the Resident's role and persona", () => {
    const [assigned] = payloadsOf(events, "role_assigned");
    const { resident, role, persona } = found(assigned, "role assignment");
    render(<GameConsole events={events} connection="ended" />);

    const mind = inspect(resident);

    expect(mind).toHaveTextContent(new RegExp(role, "i"));
    for (const trait of [persona.occupation, persona.temperament, persona.speaking_style, persona.quirk]) {
      expect(mind).toHaveTextContent(trait);
    }
  });

  it("shows the notebook, journal and dossier as of the moment being viewed", () => {
    const first = found(notes.find((note) => note.payload.notebook && note.payload.suspicions.length), "notes");
    const writer = first.payload.resident;
    const later = found(
      notes.find((note) => note.payload.resident === writer && note.seq > first.seq && note.payload.notebook),
      "later notes",
    );
    const view = render(<GameConsole events={upTo(first.seq)} connection="live" />);

    const mind = inspect(writer);
    expect(section(mind, "Notebook")).toHaveTextContent(first.payload.notebook);
    const entries = notes.filter((n) => n.payload.resident === writer && n.seq <= first.seq && n.payload.journal_entry);
    const journal = within(mind).getByRole("list", { name: "Journal" });
    expect(within(journal).getAllByRole("listitem")).toHaveLength(entries.length);
    const [suspicion] = first.payload.suspicions;
    const row = within(within(mind).getByRole("list", { name: "Dossier" })).getByRole("listitem", {
      name: found(suspicion, "suspicion").resident,
    });
    expect(row).toHaveTextContent(`${suspicion?.suspicion}/100: ${suspicion?.note}`);

    view.rerender(<GameConsole events={upTo(later.seq)} connection="live" />);
    const now = screen.getByRole("complementary", { name: `Mind of ${writer}` });
    expect(section(now, "Notebook")).toHaveTextContent(later.payload.notebook);
    const laterEntries = notes.filter((n) => n.payload.resident === writer && n.seq <= later.seq && n.payload.journal_entry);
    expect(within(within(now).getByRole("list", { name: "Journal" })).getAllByRole("listitem")).toHaveLength(
      laterEntries.length,
    );
    for (const changed of later.payload.suspicions) {
      const changedRow = within(within(now).getByRole("list", { name: "Dossier" })).getByRole("listitem", {
        name: changed.resident,
      });
      expect(changedRow).toHaveTextContent(`${changed.suspicion}/100: ${changed.note}`);
    }
  });

  it("keeps the previous notebook after a reflection that fell back to an empty one", () => {
    const lapse = found(
      notes.find(
        (note) =>
          !note.payload.notebook &&
          notes.some((n) => n.payload.resident === note.payload.resident && n.seq < note.seq && n.payload.notebook),
      ),
      "fallback reflection after real notes",
    );
    const before = notes.filter((n) => n.payload.resident === lapse.payload.resident && n.seq < lapse.seq);
    const kept = found(before.filter((n) => n.payload.notebook).at(-1), "earlier notebook").payload.notebook;
    render(<GameConsole events={upTo(lapse.seq)} connection="live" />);

    const mind = inspect(lapse.payload.resident);

    expect(section(mind, "Notebook")).toHaveTextContent(kept);
  });

  it("says when a Resident has no opinion yet about someone", () => {
    const first = found(notes[0], "notes");
    render(<GameConsole events={upTo(first.seq)} connection="live" />);

    const mind = inspect(first.payload.resident);
    const rows = within(within(mind).getByRole("list", { name: "Dossier" })).getAllByRole("listitem");

    const silent = rows.filter((row) => row.textContent?.includes("no opinion yet"));
    expect(silent).toHaveLength(rows.length - first.payload.suspicions.length);
  });

  it("marks every decision that fell back with its reason", () => {
    const fallback = found(eventsOf(events, "decision_fell_back")[0], "fallback");
    const resident = fallback.payload.resident;
    const reasons = payloadsOf(events, "decision_fell_back").filter((f) => f.resident === resident);
    render(<GameConsole events={events} connection="ended" />);

    const decisions = within(inspect(resident)).getByRole("list", { name: "Decisions" });

    const marked = within(decisions).getAllByText(/^fell back to a safe default: /i);
    expect(marked.map((mark) => mark.textContent)).toEqual(
      reasons.map((reason) => `fell back to a safe default: ${reason.reason}`),
    );
  });

  it("is hidden in mystery mode, which also hides private events and secret roles", () => {
    const [assigned] = payloadsOf(events, "role_assigned");
    render(<GameConsole events={events} connection="ended" />);
    inspect(found(assigned, "role assignment").resident);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    expect(screen.queryByRole("complementary", { name: /^Mind of/ })).toBeNull();
    const roster = screen.getByRole("list", { name: "Residents" });
    expect(within(roster).queryAllByRole("button")).toHaveLength(0);
    expect(roster).not.toHaveTextContent("(secret)");
    const feed = screen.getByRole("log", { name: "Town feed" });
    const kinds = new Set(within(feed).getAllByRole("listitem").map((item) => item.dataset.kind));
    expect(kinds.has("bid_placed") || kinds.has("decision_fell_back")).toBe(false);
  });

  it("shows the Open floor under way in mystery mode, though bids are private", () => {
    const firstBid = found(eventsOf(events, "bid_placed")[0], "bid");
    render(<GameConsole events={upTo(firstBid.seq)} connection="live" />);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    expect(screen.getByRole("banner")).toHaveTextContent("Open floor: 0 of 8 Statements");
  });

  it("cannot be opened on a public-scope page, where mystery mode is locked on", () => {
    render(<GameConsole events={events} connection="ended" scope="public" />);

    const roster = screen.getByRole("list", { name: "Residents" });
    expect(within(roster).queryAllByRole("button")).toHaveLength(0);
    const mystery = screen.getByRole("button", { name: "Mystery mode" });
    expect(mystery).toBeDisabled();
    expect(mystery).toHaveAttribute("aria-pressed", "true");
  });
});

describe("the why? drawer", () => {
  const ballot = found(eventsOf(events, "ballot_cast")[0], "ballot");

  function attempt(number: number, outcome: ModelCall["outcome"], rawText: string): ModelCall {
    return {
      decision_id: ballot.decision_id ?? "",
      resident: ballot.payload.voter,
      kind: "ballot",
      attempt: number,
      provider: "claude-agent-sdk",
      model: "claude-haiku-5-5",
      effort: "low",
      prompt_version: "abc123",
      system: `You are ${ballot.payload.voter}. SYSTEM-PROMPT-TEXT`,
      prompt: `USER-PROMPT-TEXT ${number}`,
      outcome,
      problem: outcome === "invalid" ? "'Nobody' is not one of the options" : null,
      raw_text: rawText,
      answer: null,
      input_tokens: 4000,
      output_tokens: 30,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      cost_usd: null,
      latency_ms: 900,
      trace_id: "0af7651916cd43dd8448eb211c80319c",
    };
  }

  function openDrawer(explanation: Explanation) {
    const explain = vi.fn((seq: number) => Promise.resolve({ ...explanation, event: eventAt(seq) }));
    render(<GameConsole events={events} connection="ended" explain={explain} />);
    const decisions = within(inspect(ballot.payload.voter)).getByRole("list", { name: "Decisions" });
    const item = within(decisions).getByRole("listitem", { name: `Decision at event ${ballot.seq}` });
    fireEvent.click(within(item).getByRole("button", { name: "why?" }));
    return { explain, item };
  }

  function eventAt(seq: number): Event {
    return found(
      events.find((event) => event.seq === seq),
      `event ${seq}`,
    );
  }

  it("shows every attempt's prompts and raw answer as plain text, flagging the retry", async () => {
    const raw = '{"choice": "<b>Nobody</b>"}';
    const { explain, item } = openDrawer({
      event: ballot,
      attempts: [attempt(1, "invalid", raw), attempt(2, "ok", '{"choice": "SKIP"}')],
      fallback_reason: null,
    });

    const drawer = await within(item).findByRole("region", { name: "Why?" });

    expect(explain).toHaveBeenCalledWith(ballot.seq);
    expect(within(drawer).getByRole("article", { name: "Attempt 2" })).toHaveTextContent("Attempt 2 (retry)");
    expect(drawer).toHaveTextContent("SYSTEM-PROMPT-TEXT");
    expect(drawer).toHaveTextContent("USER-PROMPT-TEXT 1");
    expect(drawer).toHaveTextContent("'Nobody' is not one of the options");
    expect(drawer).toHaveTextContent(raw);
    expect(drawer.querySelector("b")).toBeNull();
  });

  it("links each attempt to its trace when the Host set a trace address", async () => {
    vi.stubEnv("VITE_TRACE_URL", "https://traces.example/project/p1/traces/{traceId}");
    const { item } = openDrawer({ event: ballot, attempts: [attempt(1, "ok", "{}")], fallback_reason: null });

    const drawer = await within(item).findByRole("region", { name: "Why?" });

    expect(within(drawer).getByRole("link", { name: "trace" })).toHaveAttribute(
      "href",
      "https://traces.example/project/p1/traces/0af7651916cd43dd8448eb211c80319c",
    );
    vi.unstubAllEnvs();
  });

  it("says when a scripted bot made the decision, and why it fell back", async () => {
    const { item } = openDrawer({ event: ballot, attempts: [], fallback_reason: "lost the thread" });

    const drawer = await within(item).findByRole("region", { name: "Why?" });

    expect(drawer).toHaveTextContent("A scripted bot made this decision, so no model was asked.");
    expect(drawer).toHaveTextContent(/fell back to a safe default: lost the thread/i);
  });
});
