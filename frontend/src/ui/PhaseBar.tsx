import type { GameView } from "../core/gameView";
import type { ConnectionStatus } from "../net/followGame";
import { phaseLabel, victoryLabel } from "./labels";

const connectionLabel: Record<ConnectionStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  ended: "Finished",
};

export function PhaseBar({ view, connection }: { view: GameView; connection: ConnectionStatus }) {
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-stone-800 px-6 py-4">
      <h1 className="font-serif text-2xl text-amber-200">MurderTown</h1>
      <p className="text-lg">
        {view.day > 0 && <span className="text-stone-400">Day {view.day} · </span>}
        <span className="font-semibold">{phaseLabel[view.phase]}</span>
      </p>
      {view.outcome && (
        <p className="text-amber-300">
          <strong>{victoryLabel[view.outcome.winner]}.</strong> {view.outcome.reason}
        </p>
      )}
      <span className="ml-auto rounded-full border border-stone-700 px-3 py-1 text-sm text-stone-300">
        {connectionLabel[connection]}
      </span>
    </header>
  );
}
