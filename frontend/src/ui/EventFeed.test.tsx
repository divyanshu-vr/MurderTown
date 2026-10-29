/** Seam 3: the feed's filters, by kind of line and by Resident, on the recorded game. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Event } from "../protocol";
import { NIGHT_LINES, PRIVATE_LINES } from "../../test/feedLines";
import { payloadsOf, recordedGame } from "../../test/recordedGame";
import { inFeed } from "./describeEvent";
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
