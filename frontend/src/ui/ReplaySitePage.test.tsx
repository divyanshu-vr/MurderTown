/** The replay site's landing page: the recorded games it holds, to watch in full scope or in Mystery mode. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SiteGame } from "../net/replaySite";
import { gameFileAt } from "./paths";
import { SiteGames } from "./ReplaySitePage";

const games: SiteGame[] = [
  { file: "games/first.ndjson", title: "The baker's bluff", blurb: "Eight Residents, two Murderers." },
  { file: "games/second.ndjson", title: "A Detective always right", blurb: "And still not believed." },
];

describe("the replay site's games", () => {
  it("lists each game, to watch in full or in Mystery mode", () => {
    render(<SiteGames games={games} />);

    const listed = within(screen.getByRole("list", { name: "Recorded games" })).getAllByRole("listitem");
    expect(listed).toHaveLength(2);
    const first = within(listed[0] as HTMLElement);
    expect(first.getByRole("heading", { name: "The baker's bluff" })).toBeVisible();
    expect(first.getByText("Eight Residents, two Murderers.")).toBeVisible();
    const watch = first.getByRole("link", { name: "Watch" }).getAttribute("href") ?? "";
    const mystery = first.getByRole("link", { name: "Watch in Mystery mode" }).getAttribute("href") ?? "";
    expect(gameFileAt(new URL(watch, "http://site"))).toEqual({ file: "/site/games/first.ndjson", mystery: false });
    expect(gameFileAt(new URL(mystery, "http://site"))).toEqual({ file: "/site/games/first.ndjson", mystery: true });
  });
});
