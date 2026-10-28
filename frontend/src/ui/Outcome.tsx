import type { Outcome } from "../core/gameView";
import { victoryLabel } from "./labels";

/** How a game's end reads, wherever it is shown: who won and why, or why it was aborted. */
export function OutcomeText({ outcome }: { outcome: Outcome }) {
  return outcome.ended === "won" ? (
    <>
      <strong>{victoryLabel[outcome.winner]}.</strong> {outcome.reason}
    </>
  ) : (
    <>
      <strong>Game aborted:</strong> {outcome.reason}
    </>
  );
}
