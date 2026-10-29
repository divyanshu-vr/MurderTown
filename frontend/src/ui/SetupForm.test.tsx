/** The setup form: the Host chooses a game's rules, seed and lineup, within the protocol's bounds. */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { defaultConfig } from "../core/setup";
import type { Estimate, GameConfigInput, SetupChoices } from "../protocol";
import { ESTIMATE_AFTER_MS, SetupForm } from "./SetupForm";

const choices: SetupChoices = {
  providers: ["scripted", "claude", "anthropic"],
  models: ["claude-haiku-5-5", "claude-sonnet-5-5"],
};

const SONNET_MURDERERS: Estimate = {
  usd: 0.7571,
  by_model: { "claude-haiku-5-5": 0.1684, "claude-sonnet-5-5": 0.5887 },
  days: 3,
};

function setUp(
  onStart: (config: GameConfigInput) => Promise<void> = () => Promise.resolve(),
  estimate: (config: GameConfigInput) => Promise<Estimate> = () => Promise.resolve(SONNET_MURDERERS),
) {
  const started: GameConfigInput[] = [];
  render(
    <SetupForm
      choices={choices}
      onStart={(config) => {
        started.push(config);
        return onStart(config);
      }}
      estimate={estimate}
    />,
  );
  return started;
}

function start() {
  fireEvent.click(screen.getByRole("button", { name: "Start the game" }));
}

function choose(group: HTMLElement, label: string, value: string) {
  fireEvent.change(within(group).getByRole("combobox", { name: label }), { target: { value } });
}

describe("the setup form", () => {
  it("bounds the numbers as the server does", () => {
    setUp();

    const residents = screen.getByRole("spinbutton", { name: "Residents" });
    expect([residents.getAttribute("min"), residents.getAttribute("max")]).toEqual(["6", "15"]);
    const accuracy = screen.getByRole("spinbutton", { name: "Detective accuracy" });
    expect([accuracy.getAttribute("min"), accuracy.getAttribute("max"), accuracy.getAttribute("step")]).toEqual([
      "0.5",
      "1",
      "any",
    ]);
  });

  it("starts a game from the server's defaults, leaving the seed for the server to draw", () => {
    const started = setUp();

    start();

    expect(started).toEqual([defaultConfig()]);
  });

  it("will not start a game with a number out of bounds, and says which", () => {
    const started = setUp();

    fireEvent.change(screen.getByRole("spinbutton", { name: "Residents" }), { target: { value: "20" } });
    start();

    expect(screen.getByText("Residents: at most 15")).toBeInTheDocument();
    expect(started).toEqual([]);
  });

  it("puts in a chosen seed, no time limit, and a model for the Murderers", () => {
    const started = setUp();

    fireEvent.change(screen.getByRole("textbox", { name: "Seed" }), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "No time limit" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "The Murderers play differently" }));
    const murderers = screen.getByRole("group", { name: "Murderers" });
    choose(murderers, "Provider", "claude");
    choose(murderers, "Model", "claude-sonnet-5-5");
    start();

    expect(started[0]).toMatchObject({
      seed: 42,
      open_floor_seconds: null,
      lineup: { murderers: { provider: "claude", model: "claude-sonnet-5-5", effort: "low" } },
    });
  });

  it("lets one seat be played differently", () => {
    const started = setUp();

    fireEvent.click(screen.getByRole("button", { name: "Add a seat" }));
    const seat = screen.getByRole("group", { name: "One seat" });
    choose(seat, "Seat", "3");
    choose(seat, "Provider", "anthropic");
    start();

    expect(started[0]?.lineup?.seats).toEqual({ "3": { provider: "anthropic", model: "claude-haiku-5-5", effort: "low" } });
  });

  it("shows the server's reason when it refuses", async () => {
    const refusal = "The server could not start the game (422): 3 Murderers is more than a quarter of 8 Residents";
    setUp(() => Promise.reject(new Error(refusal)));

    start();

    expect(await screen.findByRole("alert")).toHaveTextContent(refusal);
  });

  it("shows what the setup is expected to cost, and each model's share", async () => {
    setUp();

    const cost = await screen.findByRole("status", { name: "Expected cost" });
    expect(cost).toHaveTextContent("About $0.76 equivalent for a game of 3 Days");
    expect(cost).toHaveTextContent("claude-haiku-5-5 $0.17 · claude-sonnet-5-5 $0.59");
    expect(cost).toHaveTextContent("costs nothing extra but uses its quota");
  });

  it("says why there is no estimate when the server refuses the setup", async () => {
    setUp(undefined, () => Promise.reject(new Error("3 Murderers is more than a quarter of 12 Residents")));

    const cost = await screen.findByRole("status", { name: "Expected cost" });
    expect(cost).toHaveTextContent("No estimate: 3 Murderers is more than a quarter of 12 Residents");
  });

  it("says a scripted setup costs nothing", async () => {
    setUp(undefined, () => Promise.resolve({ usd: 0, by_model: {}, days: 5 }));

    const cost = await screen.findByRole("status", { name: "Expected cost" });
    expect(cost).toHaveTextContent("Costs nothing: every Resident is scripted.");
    expect(cost).not.toHaveTextContent("quota");
  });

  it("asks again when the setup changes, but not while it has a problem", async () => {
    const asked: GameConfigInput[] = [];
    setUp(undefined, (config) => {
      asked.push(config);
      return Promise.resolve(SONNET_MURDERERS);
    });
    const residents = screen.getByRole("spinbutton", { name: "Residents" });

    fireEvent.change(residents, { target: { value: "8" } });
    await waitFor(() => expect(asked.at(-1)?.residents).toBe(8));
    fireEvent.change(residents, { target: { value: "20" } });

    await new Promise((resolve) => setTimeout(resolve, ESTIMATE_AFTER_MS * 2));
    expect(asked.map((config) => config.residents)).not.toContain(20);
    expect(screen.queryByRole("status", { name: "Expected cost" })).toBeNull();
  });
});
