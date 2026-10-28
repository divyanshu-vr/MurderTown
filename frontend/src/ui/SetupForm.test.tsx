/** The setup form: the Host chooses a game's rules, seed and lineup, within the protocol's bounds. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { defaultConfig } from "../core/setup";
import type { GameConfigInput, SetupChoices } from "../protocol";
import { SetupForm } from "./SetupForm";

const choices: SetupChoices = {
  providers: ["scripted", "claude", "anthropic"],
  models: ["claude-haiku-5-5", "claude-sonnet-5-5"],
};

function setUp(onStart: (config: GameConfigInput) => Promise<void> = () => Promise.resolve()) {
  const started: GameConfigInput[] = [];
  render(
    <SetupForm
      choices={choices}
      onStart={(config) => {
        started.push(config);
        return onStart(config);
      }}
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
});
