/** Seam 3: the feed's filters, by kind of line and by Resident, on the recorded game. */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Event } from "../protocol";
import { NIGHT_LINES, PRIVATE_LINES } from "../../test/feedLines";
import { present } from "../../test/present";
import { eventsOf, payloadsOf, recordedGame } from "../../test/recordedGame";
import { EVERYTHING, offeredKinds } from "../core/feedFilter";
import { TYPING_PER_SECOND } from "../core/presentation";
import { describeEvent, inFeed } from "./describeEvent";
import { EventFeed, type Typing } from "./EventFeed";
import { GameConsole } from "./GameConsole";

const events = recordedGame();

type Kind = Event["payload"]["type"];

function lines() {
  return within(screen.getByRole("log", { name: "Town feed" })).getAllByRole("listitem");
}

const isHeading = (line: HTMLElement) => line.dataset.kind === "phase_started";

/** The lines shown, leaving out the Phase headings above them. */
function withoutHeadings() {
  return lines().filter((line) => !isHeading(line));
}

/** Leave only `wanted` of the kinds of line on. */
function showOnly(wanted: string) {
  for (const toggle of within(screen.getByRole("group", { name: "Show" })).getAllByRole("button")) {
    const on = toggle.getAttribute("aria-pressed") === "true";
    if (on !== (toggle.textContent === wanted)) fireEvent.click(toggle);
  }
}

function follow(resident: string) {
  fireEvent.change(screen.getByRole("combobox", { name: "Resident" }), { target: { value: resident } });
}

/** How many of the recorded game's feed lines are of these types. */
function linesOf(kinds: readonly Kind[]): number {
  return events.filter(inFeed).filter(({ payload }) => kinds.includes(payload.type)).length;
}

/** Every Phase heading shown has a line under it. */
function expectNoEmptyHeadings() {
  const shown = lines();
  shown.forEach((line, index) => {
    if (isHeading(line)) expect(shown[index + 1] && !isHeading(shown[index + 1] as HTMLElement)).toBe(true);
  });
}

describe("the feed's filters", () => {
  it("show only the Night's secret actions when only Night is chosen, under their Phases", () => {
    render(<GameConsole events={events} connection="ended" />);

    showOnly("Night");

    expect(new Set(withoutHeadings().map((line) => line.dataset.kind))).toEqual(new Set(NIGHT_LINES));
    expect(withoutHeadings()).toHaveLength(linesOf(NIGHT_LINES));
    expect(lines().filter(isHeading).length).toBeGreaterThan(0);
    expectNoEmptyHeadings();
  });

  it("show only what some saw in private when only Private is chosen", () => {
    render(<GameConsole events={events} connection="ended" />);

    showOnly("Private");

    expect(new Set(withoutHeadings().map((line) => line.dataset.kind))).toEqual(new Set(PRIVATE_LINES));
    expect(withoutHeadings()).toHaveLength(linesOf(PRIVATE_LINES));
  });

  it("show one Resident's lines, under the Day and Phase each happened in", () => {
    render(<GameConsole events={events} connection="ended" />);
    const resident = payloadsOf(events, "role_assigned")[0]?.resident ?? "";

    follow(resident);

    const [reveal, ...rest] = withoutHeadings().reverse();
    expect(reveal?.dataset.kind).toBe("roles_revealed"); // it tells their role, even when it does not name them
    for (const line of rest) expect(line).toHaveTextContent(resident);
    const said = payloadsOf(events, "statement_made").filter((statement) => statement.speaker === resident);
    const theirs = withoutHeadings().filter((line) => line.textContent?.startsWith(`${resident}: "`));
    expect(theirs).toHaveLength(said.length);
    expectNoEmptyHeadings();
  });

  it("combine a kind with a Resident: a Murderer's Night", () => {
    render(<GameConsole events={events} connection="ended" />);
    const murderer = payloadsOf(events, "role_assigned").find((assigned) => assigned.role === "murderer");
    const name = murderer?.resident ?? "";

    showOnly("Night");
    follow(name);

    expect(withoutHeadings().length).toBeGreaterThan(0);
    for (const line of withoutHeadings()) {
      expect(NIGHT_LINES).toContain(line.dataset.kind);
      expect(line).toHaveTextContent(name);
    }
  });

  it("last while another tab is open", () => {
    render(<GameConsole events={events} connection="ended" />);
    showOnly("Night");
    const night = lines().length;

    fireEvent.click(screen.getByRole("tab", { name: "Suspicion" }));
    fireEvent.click(screen.getByRole("tab", { name: "Feed" }));

    expect(lines()).toHaveLength(night);
  });

  it("show the whole town's lines again on entering mystery mode, keeping the Resident followed", () => {
    render(<GameConsole events={events} connection="ended" />);
    const resident = payloadsOf(events, "role_assigned")[0]?.resident ?? "";
    showOnly("Night");
    follow(resident);

    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));

    const toggles = within(screen.getByRole("group", { name: "Show" })).getAllByRole("button");
    expect(toggles.every((toggle) => toggle.getAttribute("aria-pressed") === "true")).toBe(true);
    expect(screen.getByRole("combobox", { name: "Resident" })).toHaveValue(resident);
    expect(withoutHeadings().length).toBeGreaterThan(0);
  });

  it.each([
    ["in mystery mode", "full", true],
    ["on a public page", "public", false],
  ] as const)("offer %s only what the whole town saw and the game's notices", (_, scope, mystery) => {
    render(<GameConsole events={events} connection="ended" scope={scope} startsInMystery={mystery} />);

    const offered = within(screen.getByRole("group", { name: "Show" })).getAllByRole("button");
    expect(offered.map((toggle) => toggle.textContent)).toEqual(["Public", "System"]);
  });

  it("show everything again once cleared", () => {
    render(<GameConsole events={events} connection="ended" />);
    const everything = lines().length;
    showOnly("Night");
    follow(payloadsOf(events, "role_assigned")[0]?.resident ?? "");

    fireEvent.click(screen.getByRole("button", { name: "Show everything" }));

    expect(lines()).toHaveLength(everything);
    expect(screen.queryByRole("button", { name: "Show everything" })).toBeNull();
  });
});

describe("words in the feed", () => {
  afterEach(() => vi.useRealTimers());

  const statement = present(eventsOf(events, "statement_made")[0], "a Statement");
  const upToIt = events.filter(({ seq }) => seq <= statement.seq);
  const whole = describeEvent(statement);

  function feed(typing: Typing) {
    return <EventFeed events={upToIt} residents={[]} kinds={offeredKinds(false)} filter={EVERYTHING} onFilterChange={() => undefined} typing={typing} />;
  }

  /** The newest line's words on screen so far; the rest keeps its place, unseen. */
  function typedSoFar(): string {
    const words = lines().at(-1)?.querySelector('[aria-hidden="true"]');
    const unseen = words?.querySelector(".invisible")?.textContent ?? "";
    const all = words?.textContent ?? "";
    return all.slice(0, all.length - unseen.length);
  }

  it("type out the newest at playback's pace, stand still while held, and read whole to a screen reader", () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] });
    const { rerender } = render(feed({ pace: 2, held: false }));
    expect(lines().at(-1)?.querySelector(".sr-only")?.textContent).toBe(whole);
    expect(typedSoFar()).toBe("");

    act(() => vi.advanceTimersByTime(250));
    const afterAQuarterSecond = typedSoFar().length;
    expect(afterAQuarterSecond).toBeGreaterThan(TYPING_PER_SECOND * 2 * 0.2);
    expect(afterAQuarterSecond).toBeLessThan(TYPING_PER_SECOND * 2 * 0.3);
    expect(whole.startsWith(typedSoFar())).toBe(true);

    rerender(feed({ pace: 2, held: true }));
    act(() => vi.advanceTimersByTime(1000));
    expect(typedSoFar().length).toBe(afterAQuarterSecond);

    rerender(feed({ pace: 2, held: false }));
    act(() => vi.advanceTimersByTime(60_000));
    expect(typedSoFar()).toBe(whole);
  });

  it("show whole when they appear while held, and once a newer line comes", () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] });
    const { rerender } = render(feed({ pace: 1, held: true }));
    expect(typedSoFar()).toBe(whole);

    rerender(feed({ pace: 1, held: false }));
    expect(typedSoFar()).toBe(whole); // it does not start over when play resumes
  });

  it("show whole without playback to type them", () => {
    render(<EventFeed events={upToIt} residents={[]} kinds={offeredKinds(false)} filter={EVERYTHING} onFilterChange={() => undefined} />);

    expect(lines().at(-1)?.textContent).toBe(whole);
  });
});
