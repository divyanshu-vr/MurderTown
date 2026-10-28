import type { ReactNode } from "react";

import type { GameView } from "../core/gameView";
import type { ConnectionStatus } from "../net/followGame";
import { phaseLabel, victoryLabel } from "./labels";

const connectionLabel: Record<ConnectionStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  ended: "Finished",
  refused: "Host token refused",
};

/**
 * The Day, the Phase, Open-floor progress, whether the Host has paused the game, and the
 * outcome (a win, or an abort and its reason), plus the Host's controls and the mystery-mode
 * switch. Without `onMysteryChange` the switch is locked, as it is for a public-scope page.
 */
export function PhaseBar({
  view,
  connection,
  mystery,
  onMysteryChange,
  paused = false,
  controls,
}: {
  view: GameView;
  connection: ConnectionStatus;
  mystery: boolean;
  onMysteryChange?: ((on: boolean) => void) | undefined;
  paused?: boolean;
  controls?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-stone-800 px-6 py-4">
      <h1 className="font-serif text-2xl text-amber-200">MurderTown</h1>
      <p className="text-lg">
        {view.day > 0 && <span className="text-stone-400">Day {view.day} · </span>}
        <span className="font-semibold">{phaseLabel[view.phase]}</span>
      </p>
      {view.rules && view.openFloorStatements !== null && (
        <p className="text-stone-300">
          Open floor: {view.openFloorStatements} of {view.rules.open_floor_statements} Statements
        </p>
      )}
      {paused && (
        <p className="rounded-full bg-amber-300/15 px-3 py-1 text-sm font-semibold text-amber-200">Paused</p>
      )}
      {view.outcome?.ended === "won" && (
        <p className="text-amber-300">
          <strong>{victoryLabel[view.outcome.winner]}.</strong> {view.outcome.reason}
        </p>
      )}
      {view.outcome?.ended === "aborted" && (
        <p role="alert" className="text-rose-300">
          <strong>Game aborted:</strong> {view.outcome.reason}
        </p>
      )}
      <div className="ml-auto flex items-center gap-3">
        {controls}
        <button
          type="button"
          aria-pressed={mystery}
          disabled={!onMysteryChange}
          title="Show only what the whole town saw"
          onClick={() => onMysteryChange?.(!mystery)}
          className="rounded-full border border-stone-700 px-3 py-1 text-sm text-stone-300 enabled:hover:border-amber-300 aria-pressed:bg-stone-800 aria-pressed:text-amber-200 disabled:opacity-70"
        >
          Mystery mode
        </button>
        <span className="rounded-full border border-stone-700 px-3 py-1 text-sm text-stone-300">
          {connectionLabel[connection]}
        </span>
      </div>
    </header>
  );
}
