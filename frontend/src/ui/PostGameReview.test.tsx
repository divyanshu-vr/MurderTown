/** Seam 3: the post-game review, from the recorded game and the review the server wrote beside it. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { recordedGame, recordedReview } from "../../test/recordedGame";
import { GameConsole } from "./GameConsole";
import { roleLabel, victoryLabel } from "./labels";
import type { PlaybackView } from "./usePlayback";

const events = recordedGame();
const review = recordedReview();

/** A playback that has shown the first `shown` events. */
function reached(shown: number): PlaybackView {
  const nothing = () => undefined;
  return {
    shown,
    behind: events.length - shown,
    speed: 1,
    held: true,
    live: false,
    play: nothing,
    hold: nothing,
    next: nothing,
    previous: nothing,
    seek: nothing,
    setSpeed: nothing,
    skipToLive: nothing,
  };
}

describe("the post-game review", () => {
  it("opens at the game's end with the winner, turning points, lies beside private beliefs and influence", () => {
    render(<GameConsole events={events} connection="ended" review={review} />);

    const shown = screen.getByRole("region", { name: "Post-game review" });
    const ending = events.at(-1)?.payload;
    if (ending?.type !== "game_ended") throw new Error("The recorded game has no winner");
    expect(shown).toHaveTextContent(victoryLabel[ending.winner]);
    expect(within(shown).getAllByRole("listitem", { name: /^Turning point/ })).toHaveLength(review.turning_points.length);

    const lies = within(shown).getByRole("table", { name: "Lies told" });
    const [, ...rows] = within(lies).getAllByRole("row");
    expect(rows).toHaveLength(review.lies.length);
    review.lies.forEach((lie, index) => {
      expect(rows[index]).toHaveTextContent(lie.said);
      expect(rows[index]).toHaveTextContent(lie.kind === "false_role" ? roleLabel[lie.true_role] : lie.belief.note);
    });

    const ranking = within(within(shown).getByRole("list", { name: "Influence" })).getAllByRole("listitem");
    expect(ranking.map((item) => item.textContent?.split(":")[0])).toEqual(
      review.influence.map((resident) => resident.resident),
    );
  });

  it("waits until playback reaches the end, so it gives nothing away", () => {
    render(<GameConsole events={events} connection="ended" review={review} playback={reached(events.length - 5)} />);

    expect(screen.queryByRole("tab", { name: "Review" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Post-game review" })).toBeNull();
  });

  it("is not shown in mystery mode, nor on a public page, since it tells private beliefs", () => {
    const { unmount } = render(<GameConsole events={events} connection="ended" review={review} scope="public" />);
    expect(screen.queryByRole("tab", { name: "Review" })).toBeNull();
    unmount();

    render(<GameConsole events={events} connection="ended" review={review} />);
    fireEvent.click(screen.getByRole("button", { name: "Mystery mode" }));
    expect(screen.queryByRole("region", { name: "Post-game review" })).toBeNull();
  });
});
