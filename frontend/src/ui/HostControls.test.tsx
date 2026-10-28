/** The Host's controls, on the Host's page only: what a game being played can do next. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Control } from "../protocol";
import { HostControls } from "./HostControls";

function asking() {
  const asked: Control[] = [];
  const onControl = (control: Control) => {
    asked.push(control);
    return Promise.resolve();
  };
  return { asked, onControl };
}

describe("the Host's controls", () => {
  it("pause a running game", () => {
    const { asked, onControl } = asking();
    render(<HostControls offered={["pause"]} onControl={onControl} />);

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));

    expect(asked).toEqual(["pause"]);
    expect(screen.queryByRole("button", { name: "Step" })).toBeNull();
  });

  it("step a paused game one batch of decisions, or resume it", () => {
    const { asked, onControl } = asking();
    render(<HostControls offered={["step", "resume"]} onControl={onControl} />);

    fireEvent.click(screen.getByRole("button", { name: "Step" }));
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));

    expect(asked).toEqual(["step", "resume"]);
    expect(screen.queryByRole("button", { name: "Pause" })).toBeNull();
  });

  it("offer nothing when the server offers nothing, as once the game is over", () => {
    render(<HostControls offered={[]} onControl={asking().onControl} />);

    expect(screen.queryByRole("group", { name: "Host controls" })).toBeNull();
  });

  it("say why the server refused", async () => {
    const refusal = "The server could not pause the game (409): That game is not being played";
    render(<HostControls offered={["pause"]} onControl={() => Promise.reject(new Error(refusal))} />);

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(refusal);
  });
});
