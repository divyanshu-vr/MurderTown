import type { GameView } from "../core/gameView";
import type { ConnectionStatus } from "../net/followGame";
import { phaseLabel, victoryLabel } from "./labels";

const connectionLabel: Record<ConnectionStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  ended: "Finished",
};

/**
 * The Day, the Phase, Open-floor progress and the outcome, plus the mystery-mode switch.
 * Without `onMysteryChange` the switch is locked, as it is for a public-scope page.
 */
export function PhaseBar({
  view,
  connection,
  mystery,
  onMysteryChange,
}: {
  view: GameView;
  connection: ConnectionStatus;
  mystery: boolean;
  onMysteryChange?: ((on: boolean) => void) | undefined;
}) {
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-stone-800 px-6 py-4">
      <h1 className="font-serif text-2xl text-amber-200">MurderTown</h1>
      <p className="text-lg">
        {view.day > 0 && <span className="text-stone-400">Day {view.day} · </span>}
        <span className="font-semibold">{phaseLabel[view.phase]}</span>
      </p>
      {view.config && view.openFloorStatements !== null && (
        <p className="text-stone-300">
          Open floor: {view.openFloorStatements} of {view.config.open_floor_statements} Statements
        </p>
      )}
      {view.outcome && (
        <p className="text-amber-300">
          <strong>{victoryLabel[view.outcome.winner]}.</strong> {view.outcome.reason}
        </p>
      )}
      <div className="ml-auto flex items-center gap-3">
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
