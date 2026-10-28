import { isOver } from "../core/gameView";
import type { GameSummary } from "../protocol";
import { dollars, phaseLabel, statusLabel, victoryLabel } from "./labels";
import { gamePath, replayPath } from "./paths";

function startedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Every game at a glance, newest first, linking to where to watch it, and to its replay once
 * it is over. The server says what each game cost only to the Host, so only the Host's list
 * has a cost column.
 */
export function GameList({ games }: { games: readonly GameSummary[] }) {
  if (games.length === 0) return <p className="text-stone-400">No games yet.</p>;
  const costs = games.some((game) => game.cost_usd !== null);
  return (
    <table aria-label="Games" className="w-full text-left text-sm">
      <thead className="text-xs uppercase tracking-wider text-stone-400">
        <tr>
          <th className="py-2 font-normal">Started</th>
          <th className="font-normal">Status</th>
          <th className="font-normal">Now</th>
          <th className="font-normal">Winner</th>
          {costs && <th className="text-right font-normal">Cost</th>}
          <th className="font-normal">
            <span className="sr-only">Replay</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {games.map((game) => (
          <tr key={game.id} className="border-t border-stone-800">
            <td className="py-2">
              <a href={gamePath(game.id)} className="text-amber-200 hover:underline">
                {startedAt(game.created_at)}
              </a>
            </td>
            <td>{statusLabel[game.status]}</td>
            <td>
              {game.day > 0 && `Day ${game.day} · `}
              {phaseLabel[game.phase]}
            </td>
            <td>{game.winner && victoryLabel[game.winner]}</td>
            {costs && <td className="text-right tabular-nums">{game.cost_usd !== null && dollars(game.cost_usd)}</td>}
            <td className="text-right">
              {isOver(game.status) && (
                <a href={replayPath(game.id)} className="text-amber-200 hover:underline">
                  Replay
                </a>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
