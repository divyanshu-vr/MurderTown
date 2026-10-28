/** The game list: every game at a glance, linking to where to watch it. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { GameSummary } from "../protocol";
import { GameList } from "./GameList";

const games: GameSummary[] = [
  {
    id: "a1",
    status: "paused",
    winner: null,
    created_at: "2026-10-28T10:00:00Z",
    last_seq: 40,
    day: 2,
    phase: "discussion",
    cost_usd: 0.0123,
    controls: [],
  },
  {
    id: "b2",
    status: "finished",
    winner: "town",
    created_at: "2026-10-28T09:00:00Z",
    last_seq: 300,
    day: 4,
    phase: "ended",
    cost_usd: 0,
    controls: [],
  },
];

function rows() {
  const [, ...body] = within(screen.getByRole("table", { name: "Games" })).getAllByRole("row");
  return body;
}

describe("the game list", () => {
  it("shows each game's status, Day, Phase and winner, linking to it", () => {
    render(<GameList games={games} />);

    const [paused, finished] = rows();
    expect(paused).toHaveTextContent("Paused");
    expect(paused).toHaveTextContent("Day 2");
    expect(paused).toHaveTextContent("Discussion");
    expect(finished).toHaveTextContent("The Town wins");
    expect(within(paused as HTMLElement).getByRole("link")).toHaveAttribute("href", "/games/a1");
  });

  it("shows what each game cost, and has no cost column when the server leaves the costs out", () => {
    render(<GameList games={games} />);
    expect(rows()[0]).toHaveTextContent("$0.0123");

    const hidden = games.map((game) => ({ ...game, cost_usd: null }));
    render(<GameList games={hidden} />);
    expect(screen.getAllByRole("table", { name: "Games" })[1]).not.toHaveTextContent("Cost");
  });

  it("says when there are no games yet", () => {
    render(<GameList games={[]} />);

    expect(screen.getByText("No games yet.")).toBeInTheDocument();
  });
});
